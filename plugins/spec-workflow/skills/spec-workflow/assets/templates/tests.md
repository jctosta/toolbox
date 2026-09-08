# Test spec: <feature title>

| Field | Value |
|---|---|
| slug | <kebab-slug> |
| status | draft \| approved \| skeletons-red \| green |
| spec | ./spec.md |
| design | ./design.md |
| framework | <pytest \| vitest \| go test> |
| marker convention | `<e.g. @pytest.mark.scenario("S-NN.M") + test_TNN_Ma_name>` |

## Matrix
| Scenario | Test ID | Level | Fixture / setup | Asserts |
|---|---|---|---|---|
| S-01.1 | T-01.1a | integration | <state + hook> | <one per THEN/AND> |
| S-01.1 | T-01.1b | unit | <pure input> | <expected output> |
| S-01.2 | T-01.2a | integration | <state> | <asserts> |
| S-01.3 | T-01.3a | integration | <hook forcing failure> | <asserts> |
| X-01 | T-X01a | e2e | <load/setup> | <constraint check> |

## Fixtures to create
- <name> — <what it sets up> — <used by T-IDs>

## Manual cases
- None | T-NN.Ma — <steps> — <why not automatable>

## Notes
- <anything a tester needs that isn't in the matrix>
