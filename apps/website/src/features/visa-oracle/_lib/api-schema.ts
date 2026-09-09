// Generated operation closure from Mouth OpenAPI; see import-oracle.cjs.
export interface operations {
evaluateVisaOracleV2: {
    parameters: {
      query: {
        traffic_source: "real" | "synthetic_driver" | "synthetic_gold";
        request_category?:
          | "business"
          | "diaspora"
          | "family"
          | "investor"
          | "long_tourism"
          | "other"
          | "retirement"
          | "student"
          | "work_employee"
          | "work_remote";
      };
      header?: {
        /** @description Opaque durable replay key (max 128 ASCII) */
        "Idempotency-Key"?: string | null;
      };
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["VisaOracleEvaluateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleEvaluateResponse"];
        };
      };
      /** @description Malformed or conflicting input */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleErrorResponse"];
        };
      };
      /** @description Idempotency key conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleErrorResponse"];
        };
      };
      /** @description Request body too large */
      413: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleErrorResponse"];
        };
      };
      /** @description Unsupported media type */
      415: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleErrorResponse"];
        };
      };
      /** @description Schema validation failed without echoing input values */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["VisaOracleValidationErrorResponse"];
        };
      };
    };
  };
}
export interface components { schemas: {
VisaOracleEvaluateRequest: {
      /**
       * Assessment Id
       * Format: uuid
       */
      assessment_id: string;
      /**
       * Collected At
       * Format: date-time
       */
      collected_at: string;
      /**
       * Disclosed Review Flags
       * @default []
       */
      disclosed_review_flags: components["schemas"]["DisclosedReviewFlag"][];
      facts: components["schemas"]["ApplicantFactsData"];
      /**
       * Schema Version
       * @constant
       */
      schema_version: "1.0.0";
    };
VisaOracleEvaluateResponse: {
      decision: components["schemas"]["Decision"];
      display: components["schemas"]["VisaOracleDisplayDTO"];
      mode: components["schemas"]["EvaluateResponseMode"];
      /** Sources */
      sources: components["schemas"]["SourceRecordDTO"][];
    };
VisaOracleErrorResponse: {
      /** Detail */
      detail: string;
    };
VisaOracleValidationErrorResponse: {
      /** Detail */
      detail: components["schemas"]["VisaOracleValidationErrorItem"][];
    };
VisaOracleValidationErrorItem: {
      /** Loc */
      loc: string[];
      /** Msg */
      msg: string;
      /** Type */
      type: string;
    };
Decision: {
      /** Candidates */
      candidates: components["schemas"]["Candidate"][];
      /** Decision Id */
      decision_id: string | null;
      decision_integrity: components["schemas"]["Fingerprint"] | null;
      /**
       * Effective At
       * Format: date-time
       */
      effective_at: string;
      /**
       * Evaluated At
       * Format: date-time
       */
      evaluated_at: string;
      facts_fingerprint: components["schemas"]["Fingerprint"] | null;
      /** Missing Facts */
      missing_facts: components["schemas"]["FactPath"][];
      /** No Path Reasons */
      no_path_reasons: components["schemas"]["Reason"][];
      /** Notices */
      notices: components["schemas"]["Reason"][];
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      outage: components["schemas"]["Outage"] | null;
      /** Public Id */
      public_id: string | null;
      /** Quotes */
      quotes: components["schemas"]["PriceQuote"][];
      /** Review Reasons */
      review_reasons: components["schemas"]["Reason"][];
      rule_pack: components["schemas"]["RulePackRef"] | null;
      /**
       * Schema Version
       * @constant
       */
      schema_version: "1.0.0";
      state: components["schemas"]["DecisionState"];
      /** Trace Sha256 */
      trace_sha256: string | null;
    } & (unknown & unknown & unknown & unknown & unknown);
VisaOracleDisplayDTO: {
      /** Candidates */
      candidates: components["schemas"]["CandidateDisplayDTO"][];
    };
EvaluateResponseMode: "CURATED" | "ENGINE";
SourceRecordDTO: {
      applicability: components["schemas"]["SourceApplicabilityDTO"];
      authority_type: components["schemas"]["SourceAuthorityType"];
      /** Canonical Url */
      canonical_url: string;
      /** Document Number */
      document_number: string | null;
      freshness: components["schemas"]["SourceFreshnessDTO"];
      /** Is Primary Authority */
      is_primary_authority: boolean;
      /**
       * Legal Period From
       * Format: date-time
       */
      legal_period_from: string;
      /** Legal Period To */
      legal_period_to: string | null;
      /** Locators */
      locators: components["schemas"]["SourceLocator"][];
      /** Publisher */
      publisher: string;
      /**
       * Recorded Period From
       * Format: date-time
       */
      recorded_period_from: string;
      /**
       * Retrieved At
       * Format: date-time
       */
      retrieved_at: string;
      /** Source Key */
      source_key: string;
      /**
       * Source Record Id
       * Format: uuid
       */
      source_record_id: string;
      status: components["schemas"]["SourceStatus"];
      /** Title */
      title: string;
      /**
       * Verified At
       * Format: date-time
       */
      verified_at: string;
    };
SourceApplicabilityDTO: {
      /**
       * Effective At
       * Format: date-time
       */
      effective_at: string;
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      status: components["schemas"]["SourceApplicabilityStatus"];
    };
SourceAuthorityType:
      | "PRIMARY_LAW"
      | "IMPLEMENTING_REGULATION"
      | "OFFICIAL_PORTAL"
      | "OFFICIAL_CIRCULAR"
      | "BALI_ZERO_POLICY"
      | "PRICING_CATALOG";
SourceFreshnessDTO: {
      /**
       * Evaluated At
       * Format: date-time
       */
      evaluated_at: string;
      /** Max Age Seconds */
      max_age_seconds?: number | null;
      /** Reason Code */
      reason_code: string;
      status: components["schemas"]["SourceFreshnessStatus"];
      /**
       * Verified At
       * Format: date-time
       */
      verified_at: string;
    };
SourceLocator: {
      kind: components["schemas"]["SourceLocatorKind"];
      /** Value */
      value: string;
    };
SourceStatus: "VERIFIED" | "SUPERSEDED" | "REVOKED" | "UNAVAILABLE";
SourceLocatorKind: "ARTICLE" | "SECTION" | "PAGE" | "PARAGRAPH" | "ANCHOR";
SourceFreshnessStatus: "CURRENT" | "STALE" | "UNKNOWN";
SourceApplicabilityStatus:
      | "APPLICABLE"
      | "NOT_YET_EFFECTIVE"
      | "EXPIRED"
      | "SUPERSEDED"
      | "REVOKED"
      | "UNAVAILABLE"
      | "UNKNOWN";
CandidateDisplayDTO: {
      availability: components["schemas"]["CandidateAvailabilityDTO"];
      documentation: components["schemas"]["CandidateDocumentationDTO"];
      name: components["schemas"]["ProductNames"];
      pricing: components["schemas"]["CandidatePricingDTO"];
      processing_timeline: components["schemas"]["CandidateProcessingTimelineDTO"];
      /** Product Code */
      product_code: string;
      /**
       * Product Version Id
       * Format: uuid
       */
      product_version_id: string;
      /** Rank */
      rank: number;
      stay_policy: components["schemas"]["CandidateStayPolicyDTO"];
      tagline: components["schemas"]["ProductNames"] | null;
    };
CandidateAvailabilityDTO: {
      bali_zero_service_availability: components["schemas"]["AvailabilityAssessmentDTO"];
      /**
       * Legal Eligibility
       * @constant
       */
      legal_eligibility: "SUPPORTED";
      operational_availability: components["schemas"]["AvailabilityAssessmentDTO"];
    };
CandidateDocumentationDTO: {
      /** Checklist */
      checklist: components["schemas"]["ProductNames"][];
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      /** Reason Code */
      reason_code: string;
      /** Requirements */
      requirements: components["schemas"]["ProductNames"][];
      status: components["schemas"]["DocumentationStatus"];
    };
ProductNames: {
      /** En */
      en: string;
      /** Id */
      id: string;
    };
CandidatePricingDTO: {
      /** Catalog Last Updated */
      catalog_last_updated: string | null;
      /** Catalog Sha256 */
      catalog_sha256?: string | null;
      /**
       * Evaluated At
       * Format: date-time
       */
      evaluated_at: string;
      /** Reason Code */
      reason_code: string;
      /** Row Sha256 */
      row_sha256?: string | null;
      status: components["schemas"]["PricingAvailabilityStatus"];
    };
CandidateProcessingTimelineDTO: {
      /** Anchor Date */
      anchor_date: string | null;
      /** Estimated Completion From */
      estimated_completion_from: string | null;
      /** Estimated Completion To */
      estimated_completion_to: string | null;
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      /** Reason Code */
      reason_code: string;
      status: components["schemas"]["ProcessingTimelineStatus"];
    };
CandidateStayPolicyDTO: {
      extension: components["schemas"]["ExtensionPolicy"];
      stay: components["schemas"]["StayPolicy"];
    };
ExtensionPolicy: {
      /** Allowed */
      allowed: boolean;
      /** Days Per Extension */
      days_per_extension: number | null;
      /** Maximum Extensions */
      maximum_extensions: number;
      /** Reason Code */
      reason_code?: string | null;
      /** Status */
      status?: ("VERIFIED" | "UNKNOWN") | null;
    };
StayPolicy: {
      kind: components["schemas"]["StayPolicyKind"];
      /** Maximum Days */
      maximum_days: number | null;
      /** Minimum Days */
      minimum_days: number | null;
    };
StayPolicyKind: "FIXED_DAYS" | "VARIABLE_BY_GRANT" | "NOT_APPLICABLE";
ProcessingTimelineStatus: "AVAILABLE" | "UNKNOWN";
PricingAvailabilityStatus:
      "AVAILABLE" | "CONTACT_REQUIRED" | "UNAVAILABLE" | "UNKNOWN";
DocumentationStatus: "AVAILABLE" | "UNKNOWN";
AvailabilityAssessmentDTO: {
      /**
       * Observed At
       * Format: date-time
       */
      observed_at: string;
      /** Reason Code */
      reason_code: string;
      /**
       * Source Refs
       * @default []
       */
      source_refs: string[];
      status: components["schemas"]["AvailabilityStatus"];
    };
AvailabilityStatus: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN";
Candidate: {
      /** Covered Purposes */
      covered_purposes: string[];
      /** Product Code */
      product_code: string;
      /**
       * Product Version Id
       * Format: uuid
       */
      product_version_id: string;
      /** Rank */
      rank: number;
      /** Reason Codes */
      reason_codes: string[];
      /** Score */
      score: number;
      /** Source Refs */
      source_refs: string[];
      /** Support Rule Ids */
      support_rule_ids: string[];
    };
Fingerprint: {
      /**
       * Algorithm
       * @constant
       */
      algorithm: "HMAC-SHA256";
      /** Digest */
      digest: string;
      /** Key Id */
      key_id: string;
    };
FactPath:
      | "person.birth_date"
      | "person.nationalities"
      | "person.marital_status"
      | "immigration.currently_in_indonesia"
      | "immigration.current_status_code"
      | "immigration.current_status_expiry"
      | "immigration.last_entry_date"
      | "immigration.overstay_days"
      | "immigration.violation_history"
      | "immigration.renewal_paid"
      | "intent.purposes"
      | "intent.stay_days"
      | "intent.desired_entry_date"
      | "intent.entry_pattern"
      | "intent.requested_product_code"
      | "work.employer_country_code"
      | "work.employer_is_indonesian_entity"
      | "work.serves_indonesian_clients"
      | "work.indonesia_source_compensation"
      | "work.indonesian_work_sponsor_confirmed"
      | "investment.pt_pma_committed"
      | "investment.investment_capital_idr"
      | "investment.paid_up_capital_idr"
      | "investment.proposed_role"
      | "family.relation_to_sponsor"
      | "family.sponsor_nationalities"
      | "family.sponsor_status_code"
      | "family.marriage_registered"
      | "family.sponsor_confirmed"
      | "family.stepchild_marriage_certificate_confirmed"
      | "family.stepchild_birth_certificate_confirmed"
      | "family.sponsor_permit_basis"
      | "study.level"
      | "study.admission_confirmed"
      | "study.sponsor_confirmed"
      | "sponsor.type"
      | "secondhome.bank_deposit_usd"
      | "secondhome.bank_deposit_at_state_bank"
      | "secondhome.bank_deposit_in_own_name"
      | "secondhome.qualifying_property_value_usd"
      | "secondhome.passive_monthly_income_usd"
      | "process.application_channel"
      | "process.wants_onshore_conversion"
      | "commercial.service_fee_budget_idr"
      | "commercial.wants_quote"
      | "derived.age_years"
      | "derived.is_minor"
      | "derived.has_indonesian_citizenship"
      | "derived.has_active_stay_permit";
Reason: {
      /** Code */
      code: string;
      /** Rule Ids */
      rule_ids: string[];
      /** Source Refs */
      source_refs: string[];
    };
Outage: {
      /** Code */
      code: string;
      /** Retryable */
      retryable: boolean;
    };
PriceQuote: {
      /** Amount */
      amount: number | null;
      /** Catalog Sha256 */
      catalog_sha256: string | null;
      /** Catalog Version */
      catalog_version: string | null;
      /**
       * Currency
       * @constant
       */
      currency: "IDR";
      pricing_key: components["schemas"]["PricingKey"];
      /** Product Code */
      product_code: string;
      /**
       * Product Version Id
       * Format: uuid
       */
      product_version_id: string;
      /**
       * Quote Id
       * Format: uuid
       */
      quote_id: string;
      /**
       * Quoted At
       * Format: date-time
       */
      quoted_at: string;
      /** Reason Code */
      reason_code: string;
      /** Row Sha256 */
      row_sha256: string | null;
      /**
       * Status
       * @enum {string}
       */
      status: "AVAILABLE" | "CONTACT_REQUIRED" | "UNAVAILABLE";
      /** Valid Until */
      valid_until: string | null;
    };
RulePackRef: {
      /** Payload Sha256 */
      payload_sha256: string;
      /**
       * Rule Pack Id
       * Format: uuid
       */
      rule_pack_id: string;
      /** Sequence */
      sequence: number;
      /** Version */
      version: string;
    };
DecisionState:
      | "NEEDS_INPUT"
      | "SUPPORTED_CANDIDATES"
      | "HUMAN_REVIEW_REQUIRED"
      | "NO_SUPPORTED_PATH"
      | "TEMPORARILY_UNAVAILABLE";
PricingKey: {
      /** Category */
      category: string;
      /** Item Key */
      item_key: string;
    };
DisclosedReviewFlag:
      | "CRIMINAL_RECORD"
      | "HEALTH_CONCERN"
      | "PRIOR_VISA_REFUSAL"
      | "NOT_CERTAIN"
      | "PEP_OR_SANCTIONS"
      | "SOURCE_OF_FUNDS_UNCLEAR"
      | "DIPLOMATIC_PASSPORT"
      | "AMBIGUOUS_SPONSOR"
      | "ACTIVITY_BOUNDARY"
      | "MULTI_PURPOSE_TRIP"
      | "CONFLICTING_IMMIGRATION_STATUS";
ApplicantFactsData: {
      /** Commercial.Service Fee Budget Idr */
      "commercial.service_fee_budget_idr":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownMoney"];
      /** Commercial.Wants Quote */
      "commercial.wants_quote":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Family.Marriage Registered */
      "family.marriage_registered":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Family.Relation To Sponsor */
      "family.relation_to_sponsor":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownRelation"];
      /** Family.Sponsor Confirmed */
      "family.sponsor_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Family.Sponsor Nationalities */
      "family.sponsor_nationalities":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownCountrySet"];
      /**
       * Family.Sponsor Permit Basis
       * @default {
       *       "reason": "NOT_ASKED",
       *       "status": "UNKNOWN"
       *     }
       */
      "family.sponsor_permit_basis":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownSponsorPermitBasis"];
      /** Family.Sponsor Status Code */
      "family.sponsor_status_code":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownString"];
      /**
       * Family.Stepchild Birth Certificate Confirmed
       * @default {
       *       "reason": "NOT_ASKED",
       *       "status": "UNKNOWN"
       *     }
       */
      "family.stepchild_birth_certificate_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /**
       * Family.Stepchild Marriage Certificate Confirmed
       * @default {
       *       "reason": "NOT_ASKED",
       *       "status": "UNKNOWN"
       *     }
       */
      "family.stepchild_marriage_certificate_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Immigration.Current Status Code */
      "immigration.current_status_code":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownString"];
      /** Immigration.Current Status Expiry */
      "immigration.current_status_expiry":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownDate"];
      /** Immigration.Currently In Indonesia */
      "immigration.currently_in_indonesia":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Immigration.Last Entry Date */
      "immigration.last_entry_date":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownDate"];
      /** Immigration.Overstay Days */
      "immigration.overstay_days":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownNonNegativeInteger"];
      /**
       * Immigration.Renewal Paid
       * @default {
       *       "reason": "NOT_ASKED",
       *       "status": "UNKNOWN"
       *     }
       */
      "immigration.renewal_paid":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Immigration.Violation History */
      "immigration.violation_history":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownViolationSet"];
      /** Intent.Desired Entry Date */
      "intent.desired_entry_date":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownDate"];
      /** Intent.Entry Pattern */
      "intent.entry_pattern":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownEntryPattern"];
      /** Intent.Purposes */
      "intent.purposes":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownPurposeSet"];
      /** Intent.Requested Product Code */
      "intent.requested_product_code":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownString"];
      /** Intent.Stay Days */
      "intent.stay_days":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownNonNegativeInteger"];
      /** Investment.Investment Capital Idr */
      "investment.investment_capital_idr":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownMoney"];
      /** Investment.Paid Up Capital Idr */
      "investment.paid_up_capital_idr":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownMoney"];
      /** Investment.Proposed Role */
      "investment.proposed_role":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownProposedRole"];
      /** Investment.Pt Pma Committed */
      "investment.pt_pma_committed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Person.Birth Date */
      "person.birth_date":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownDate"];
      /** Person.Marital Status */
      "person.marital_status":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownMaritalStatus"];
      /** Person.Nationalities */
      "person.nationalities":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownCountrySet"];
      /** Process.Application Channel */
      "process.application_channel":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownApplicationChannel"];
      /** Process.Wants Onshore Conversion */
      "process.wants_onshore_conversion":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Secondhome.Bank Deposit At State Bank */
      "secondhome.bank_deposit_at_state_bank":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Secondhome.Bank Deposit In Own Name */
      "secondhome.bank_deposit_in_own_name":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Secondhome.Bank Deposit Usd */
      "secondhome.bank_deposit_usd":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownNonNegativeInteger"];
      /** Secondhome.Passive Monthly Income Usd */
      "secondhome.passive_monthly_income_usd":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownNonNegativeInteger"];
      /** Secondhome.Qualifying Property Value Usd */
      "secondhome.qualifying_property_value_usd":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownNonNegativeInteger"];
      /**
       * Sponsor.Type
       * @default {
       *       "reason": "NOT_ASKED",
       *       "status": "UNKNOWN"
       *     }
       */
      "sponsor.type":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownSponsorType"];
      /** Study.Admission Confirmed */
      "study.admission_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Study.Level */
      "study.level":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownStudyLevel"];
      /** Study.Sponsor Confirmed */
      "study.sponsor_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Work.Employer Country Code */
      "work.employer_country_code":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownCountryCode"];
      /** Work.Employer Is Indonesian Entity */
      "work.employer_is_indonesian_entity":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Work.Indonesia Source Compensation */
      "work.indonesia_source_compensation":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Work.Indonesian Work Sponsor Confirmed */
      "work.indonesian_work_sponsor_confirmed":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
      /** Work.Serves Indonesian Clients */
      "work.serves_indonesian_clients":
        | components["schemas"]["UnknownFact"]
        | components["schemas"]["KnownBoolean"];
    };
UnknownFact: {
      reason: components["schemas"]["UnknownReason"];
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "UNKNOWN";
    };
KnownMoney: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: number;
    };
KnownBoolean: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: boolean;
    };
KnownRelation: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["RelationType"];
    };
KnownCountrySet: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: string[];
    };
KnownSponsorPermitBasis: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["SponsorPermitBasis"];
    };
KnownString: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: string;
    };
KnownDate: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: string;
    };
KnownNonNegativeInteger: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: number;
    };
KnownViolationSet: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: components["schemas"]["ViolationType"][];
    };
KnownEntryPattern: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["EntryPattern"];
    };
KnownPurposeSet: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: components["schemas"]["VisaPurpose"][];
    };
KnownProposedRole: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["ProposedRole"];
    };
KnownMaritalStatus: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["MaritalStatus"];
    };
KnownApplicationChannel: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["ApplicationChannel"];
    };
KnownSponsorType: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["SponsorType"];
    };
KnownStudyLevel: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      value: components["schemas"]["StudyLevel"];
    };
KnownCountryCode: {
      /**
       * @description discriminator enum property added by openapi-typescript
       * @enum {string}
       */
      status: "KNOWN";
      /** Value */
      value: string;
    };
StudyLevel:
      | "PRIMARY"
      | "SECONDARY"
      | "VOCATIONAL"
      | "UNDERGRADUATE"
      | "POSTGRADUATE"
      | "RESEARCH"
      | "OTHER";
SponsorType:
      | "NONE"
      | "INDIVIDUAL"
      | "EMPLOYER"
      | "EDUCATION"
      | "INVESTMENT"
      | "GOVERNMENT";
ApplicationChannel: "OFFSHORE" | "ONSHORE_CONVERSION" | "STATUS_BRIDGING";
MaritalStatus: "SINGLE" | "MARRIED" | "DIVORCED" | "WIDOWED" | "OTHER";
ProposedRole:
      | "SHAREHOLDER_DIRECTOR"
      | "SHAREHOLDER_COMMISSIONER"
      | "EMPLOYEE"
      | "NO_OPERATIONAL_ROLE"
      | "OTHER";
VisaPurpose:
      | "TOURISM"
      | "BUSINESS_MEETINGS"
      | "INVESTMENT"
      | "EMPLOYMENT"
      | "REMOTE_WORK"
      | "FAMILY"
      | "STUDY"
      | "RETIREMENT"
      | "SECOND_HOME"
      | "TRANSIT"
      | "MEDICAL"
      | "OTHER";
EntryPattern: "SINGLE" | "MULTIPLE";
ViolationType:
      | "OVERSTAY"
      | "DEPORTATION"
      | "BLACKLIST"
      | "IMMIGRATION_INVESTIGATION"
      | "OTHER";
SponsorPermitBasis:
      | "EXPERT"
      | "WORKER"
      | "MARITIME_CREW"
      | "CLERGY"
      | "FOREIGN_INVESTMENT"
      | "SCIENTIFIC_RESEARCH"
      | "EDUCATION"
      | "FAMILY_REUNIFICATION"
      | "REPATRIATION"
      | "SECOND_HOME"
      | "MEDICAL_TREATMENT"
      | "WORKING_HOLIDAY"
      | "OTHER";
RelationType:
      | "SPOUSE"
      | "CHILD"
      | "PARENT"
      | "SIBLING"
      | "DEPENDENT"
      | "STEPCHILD"
      | "OTHER";
UnknownReason:
      | "NOT_ASKED"
      | "NOT_PROVIDED"
      | "UNVERIFIED"
      | "CONFLICTING"
      | "NOT_APPLICABLE";
}; }
