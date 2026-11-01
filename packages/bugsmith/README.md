# bugsmith

Deterministic JSX and CSS mutations. No model calls and no clock.

`applyOperator(operator, source, seed)` parses the file, asks the operator for one edit, and returns a unified diff. The same operator, the same source bytes, and the same seed return the same patch text. The result names the operator's archetype.

`jsxOperators` holds `remove-class`, `swap-flex-direction`, `drop-prop`, and `change-element`. `cssOperators` holds `delete-rule`, `change-unit`, `z-index`, and `overflow`. `OPERATOR_ARCHETYPE` maps each id to an archetype.

`node --test test/apply-operator.test.ts test/operators.test.ts` checks that one seed repeats, a second seed differs, and the edited snippet still parses.
