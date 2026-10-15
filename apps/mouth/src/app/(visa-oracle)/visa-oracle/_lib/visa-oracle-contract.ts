import type { components, operations } from "@/lib/api/schema";

/** Every public boundary type comes from the generated OpenAPI operation. */
export type VisaOracleEvaluateOperation = operations["evaluateVisaOracleV2"];
export type VisaOracleEvaluateRequest =
  VisaOracleEvaluateOperation["requestBody"]["content"]["application/json"];
type RawEvaluateResponse =
  VisaOracleEvaluateOperation["responses"][200]["content"]["application/json"];
type RawCandidateDisplay = components["schemas"]["CandidateDisplayDTO"];
type RawStayPolicy = components["schemas"]["StayPolicy"];

export type VisaOracleStayPolicy = Omit<RawStayPolicy, "kind"> & {
  kind: RawStayPolicy["kind"] | (string & {});
};
export type VisaOracleCandidateDisplay = Omit<
  RawCandidateDisplay,
  "stay_policy"
> & {
  stay_policy: Omit<RawCandidateDisplay["stay_policy"], "stay"> & {
    stay: VisaOracleStayPolicy;
  };
};
export type VisaOracleEvaluateResponse = Omit<
  RawEvaluateResponse,
  "display"
> & {
  display: Omit<RawEvaluateResponse["display"], "candidates"> & {
    candidates: VisaOracleCandidateDisplay[];
  };
};
export type VisaOracleErrorResponse =
  VisaOracleEvaluateOperation["responses"][400]["content"]["application/json"];
export type VisaOracleValidationErrorResponse =
  VisaOracleEvaluateOperation["responses"][422]["content"]["application/json"];

type QueryParameters = NonNullable<
  VisaOracleEvaluateOperation["parameters"]["query"]
>;

export type VisaOracleRequestCategory = NonNullable<
  QueryParameters["request_category"]
>;
export type VisaOracleApplicantFacts = VisaOracleEvaluateRequest["facts"];
export type VisaOracleFactPath = keyof VisaOracleApplicantFacts;
export type VisaOracleDisclosedReviewFlag =
  VisaOracleEvaluateRequest["disclosed_review_flags"][number];
export type VisaOracleUnknownReason = components["schemas"]["UnknownReason"];
export type VisaOracleDecisionState = components["schemas"]["DecisionState"];
export type VisaOracleSourceRecord = components["schemas"]["SourceRecordDTO"];
