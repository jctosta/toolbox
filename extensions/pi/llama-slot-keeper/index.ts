/**
 * llama-slot-keeper: keep the main model's llama.cpp prompt cache across subagent runs.
 *
 * When the main model calls a subagent tool, the extension saves the model's slot on the llama.cpp server. A router
 * with one model loaded at a time unloads the main model to run the subagent's; when the tool returns, the extension
 * loads the main model again and restores the slot before Pi sends the next request, which then reads only the new
 * tokens instead of the whole conversation.
 *
 * The server needs `--slot-save-path` (`slot-save-path` in a router preset). Environment variables:
 *   PI_SLOT_KEEPER_TOOLS      tools that hand work to another model, comma-separated (default: subagent)
 *   PI_SLOT_KEEPER_PROVIDERS  Pi providers served by llama.cpp, comma-separated (default: llama.cpp)
 *   PI_SLOT_KEEPER_SLOT       the slot that holds the main conversation (default: 0)
 *   PI_SLOT_KEEPER_DIR        the server's slot-save-path; when set, the saved files are deleted at session end
 */

import { rm } from "node:fs/promises";
import path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const LOAD_TIMEOUT_MS = 300_000;
const REQUEST_TIMEOUT_MS = 120_000;

interface Server {
	base: string;
	model: string;
	headers: Record<string, string>;
}

interface Saved extends Server {
	filename: string;
}

function names(variable: string, fallback: string): Set<string> {
	const value = process.env[variable]?.trim() || fallback;
	return new Set(
		value
			.split(",")
			.map((name) => name.trim())
			.filter(Boolean),
	);
}

const TOOLS = names("PI_SLOT_KEEPER_TOOLS", "subagent");
const PROVIDERS = names("PI_SLOT_KEEPER_PROVIDERS", "llama.cpp");
const SLOT = Number.parseInt(process.env.PI_SLOT_KEEPER_SLOT ?? "", 10) || 0;
const DIR = process.env.PI_SLOT_KEEPER_DIR?.trim() || undefined;

/** llama.cpp accepts a plain file name only: no directories, no separators. */
function safe(text: string): string {
	return text.replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 80);
}

function seconds(ms: number): string {
	return `${(ms / 1000).toFixed(1)} s`;
}

function message(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

async function request(server: Server, method: string, route: string, body?: unknown): Promise<any> {
	const response = await fetch(server.base + route, {
		method,
		headers: { "content-type": "application/json", ...server.headers },
		body: body === undefined ? undefined : JSON.stringify(body),
		signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
	});
	const text = await response.text();
	if (!response.ok) throw new Error(`${method} ${route}: HTTP ${response.status} ${text.slice(0, 200)}`);
	return text ? JSON.parse(text) : {};
}

/** The router's state for the model; undefined from a single-model server, whose one model is always loaded. */
async function state(server: Server): Promise<{ value: string; failed?: boolean } | undefined> {
	const listing = await request(server, "GET", "/models");
	const entry = (listing?.data ?? []).find((model: any) => model?.id === server.model);
	return typeof entry?.status?.value === "string" ? entry.status : undefined;
}

/** Loads the model if the router unloaded it; returns the milliseconds spent waiting. */
async function ensureLoaded(server: Server): Promise<number> {
	const start = Date.now();
	let status = await state(server);
	if (status === undefined || status.value === "loaded") return 0;
	if (status.value !== "loading") await request(server, "POST", "/models/load", { model: server.model });
	while (Date.now() - start < LOAD_TIMEOUT_MS) {
		await new Promise((resolve) => setTimeout(resolve, 250));
		status = await state(server);
		if (status === undefined || status.value === "loaded") return Date.now() - start;
		if (status.failed) throw new Error(`${server.model} failed to load`);
	}
	throw new Error(`${server.model} did not load within ${seconds(LOAD_TIMEOUT_MS)}`);
}

async function serverFor(ctx: ExtensionContext): Promise<Server | undefined> {
	const model = ctx.model;
	if (!model || !PROVIDERS.has(model.provider)) return undefined;
	const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
	const headers: Record<string, string> = {};
	if (auth.ok) {
		for (const [key, value] of Object.entries(auth.headers ?? {})) if (typeof value === "string") headers[key] = value;
		if (auth.apiKey) headers.Authorization = `Bearer ${auth.apiKey}`;
	}
	const url = new URL((auth.ok && auth.baseUrl) || model.baseUrl);
	url.pathname = url.pathname.replace(/\/+$/, "").replace(/\/v1$/, "");
	return { base: url.toString().replace(/\/+$/, ""), model: model.id, headers };
}

export default function (pi: ExtensionAPI) {
	const running = new Set<string>();
	const written = new Set<string>();
	let saved: Saved | undefined;
	let warned = false;

	const report = (ctx: ExtensionContext, text: string, level: "info" | "warning" = "info") => {
		if (ctx.hasUI) ctx.ui.notify(`llama-slot-keeper: ${text}`, level);
	};

	pi.on("tool_call", async (event, ctx) => {
		if (!TOOLS.has(event.toolName)) return;
		running.add(event.toolCallId);
		if (running.size > 1) return; // a parallel call of the same batch; the slot is saved once
		saved = undefined;
		try {
			const server = await serverFor(ctx);
			if (!server) return;
			const status = await state(server);
			if (status !== undefined && status.value !== "loaded") return; // nothing cached to keep
			const filename = `pi-${safe(ctx.sessionManager.getSessionId())}-${safe(server.model)}.bin`;
			const start = Date.now();
			const out = await request(server, "POST", `/slots/${SLOT}?action=save`, { model: server.model, filename });
			saved = { ...server, filename };
			written.add(filename);
			report(ctx, `saved ${out.n_saved ?? "?"} tokens of ${server.model} in ${seconds(Date.now() - start)}`);
		} catch (error) {
			// A tool_call handler that throws blocks the tool; a failed save only costs the re-read.
			if (!warned) report(ctx, `could not save the slot (${message(error)})`, "warning");
			warned = true;
		}
	});

	pi.on("tool_result", async (event, ctx) => {
		if (!running.delete(event.toolCallId) || running.size > 0 || !saved) return;
		const keep = saved;
		saved = undefined;
		try {
			const loadMs = await ensureLoaded(keep);
			const start = Date.now();
			const out = await request(keep, "POST", `/slots/${SLOT}?action=restore`, {
				model: keep.model,
				filename: keep.filename,
			});
			const load = loadMs ? `, after ${seconds(loadMs)} reloading the model` : "";
			report(ctx, `restored ${out.n_restored ?? "?"} tokens of ${keep.model} in ${seconds(Date.now() - start)}${load}`);
		} catch (error) {
			report(ctx, `could not restore the slot (${message(error)}); the next request reads the whole conversation`, "warning");
		}
	});

	pi.on("session_shutdown", async () => {
		const dir = DIR;
		if (!dir) return;
		await Promise.all([...written].map((file) => rm(path.join(dir, file), { force: true })));
		written.clear();
	});
}
