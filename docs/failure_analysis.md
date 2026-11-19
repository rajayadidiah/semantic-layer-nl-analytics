# Failure analysis for the November 18 live experiment

This document reviews the remaining errors after the scorer correction and offline re-scoring of
the same 200 saved model outputs. No additional LLM calls were made for this analysis.

## Corrected experiment result

| Config | Accuracy | Answerable | Unsupported | Semantic |
|---|---:|---:|---:|---:|
| A | 74.0% | 69.0% | 100.0% | 0.0% |
| B | 96.0% | 95.2% | 100.0% | 100.0% |
| C | 74.0% | 69.0% | 100.0% | 0.0% |
| D | 92.0% | 90.5% | 100.0% | 81.8% |

The remaining failures fall into four useful groups.

## 1. Missing project semantics in A and C

Configurations A and C do not receive the semantic definitions by design. Most of their
business-semantic failures therefore reflect missing information rather than malformed SQL.

Examples include q07, q08, q09, and q37-q44. For these questions the intended answer depends on
the project conventions for terms such as `valid_trip`, `trip_volume`, `average_fare`, and
`average_trip_distance`.

A and C often responded `UNSUPPORTED`, explaining that the project convention was not supplied.
That is a reasonable cautious model behavior, but it is scored as an incorrect abstention because
the benchmark question is answerable when the semantic layer is available. In other cases, the
model produced executable SQL using the raw field without the required `valid_trip` population,
creating a semantic result mismatch.

This pattern is the clearest evidence for the role of explicit semantics in this benchmark:
semantic-question accuracy was 0% for A and C, 100% for B, and 81.8% for D.

## 2. Semantic over-application in B and D

Two non-semantic temporal questions, q31 and q35, failed in both B and D.

These questions explicitly ask for recorded/raw Q1 values:

- q31 asks for monthly mean recorded base fare by service for Q1 2026 pickups.
- q35 asks for mean recorded base fare by pickup hour and service for Q1 2026.

The gold queries use only Q1 pickup membership and do not apply `valid_trip`. In B and D, however,
the model applied the full semantic validity rule, adding requirements for timestamp ordering,
positive trip distance, nonnegative fare/total, and matched non-264/265 zones.

The generated SQL was structurally valid but answered a narrower question than the benchmark.
This is an important limitation: semantic context can solve ambiguous business terms while also
encouraging the model to apply business rules to queries that intentionally request raw data.

## 3. Ordinary query-construction mistakes

A small number of errors were unrelated to the semantic layer.

- **q25 C:** the model returned an extra borough column for a top-ten pickup-zone query. The result
  therefore had the wrong number of columns.
- **q26 A:** the model omitted the requested dropoff zone name and returned only the zone ID and
  count.
- **q33 A and C:** the benchmark asks specifically for Q1 2026 pickups. A filtered by month number
  1-3 and C filtered by quarter number 1, neither of which constrains the year. Because the data
  contains timestamp anomalies, those predicates are not equivalent to the benchmark's explicit
  2026-01-01 through 2026-04-01 interval.

These are genuine output-shape or temporal-filtering mistakes.

## 4. Semantic implementation mistakes despite grounding

D still failed two business-semantic questions even though the semantic layer was present.

- **q38 D:** the model used a filtered aggregate for valid rows while retaining groups created from
  the broader raw population. This produced an extra result group and a row-count mismatch.
- **q44 D:** the model added `payment_type IS NOT NULL`, even though the project convention does
  not exclude null payment-type values. This removed a valid output group and produced a row-count
  mismatch.

These failures show that providing the correct semantic definition does not guarantee that the
model will implement every detail correctly.

## Validator interpretation

The experimental validator did not improve overall result accuracy on its own: A and C both
scored 74%. This is consistent with its intended role. It checks SQL structure, table/column
references, and prohibited operations, but it does not determine whether a valid query represents
the correct analytical meaning.

The design also intentionally has no repair loop. A rejected query is not sent back to the model
for correction. Therefore this experiment should not be interpreted as testing a full
validator-plus-repair system.

B scored 96% and D scored 92% in this run. That difference is descriptive evidence from one run,
not proof that validation is harmful.

## Unsupported questions

All four configurations scored 100% on the eight deliberately unsupported questions. The model
consistently returned `UNSUPPORTED` when the requested information was absent, including driver
identity/earnings, fuel cost, rider age, weather effects, and dispatch-to-pickup wait time.

## Scorer correction and audit trail

The first summary of the 200 model outputs reported A/B/C/D overall accuracy of
64% / 90% / 64% / 88%. Manual failure inspection found false negatives when a generated query
returned the correct values but changed both column aliases and SELECT-column order.

The scorer was changed so compact result sets can be matched across equivalent column
permutations when names do not provide a reliable alignment. Regression tests were added for the
specific alias-plus-column-order case and for offline rescoring.

The original model responses were not edited or regenerated. The saved SQL was re-executed against
the same DuckDB database and gold queries, producing the corrected 74% / 96% / 74% / 92% result.
