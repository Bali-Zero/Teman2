"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AddEvidenceParams,
  AdvanceCaseParams,
  CaseDetail,
  CaseListResponse,
  CreateCaseParams,
  ListCasesParams,
  SecondHomeSummary,
} from "@/lib/api/secondhome/secondhome.types";

const SECOND_HOME_ROOT_KEY = ["second-home"] as const;

export const secondHomeSummaryQueryKey = [
  ...SECOND_HOME_ROOT_KEY,
  "summary",
] as const;

export const secondHomeCaseListQueryKey = (params: ListCasesParams) =>
  [...SECOND_HOME_ROOT_KEY, "cases", params] as const;

export const secondHomeCaseQueryKey = (caseId: string) =>
  [...SECOND_HOME_ROOT_KEY, "case", caseId] as const;

/**
 * Console home stats: by-stage counts, active total, guarantee-due-30d, and
 * the Day-90 scanner arming state. Short staleTime — the console home is the
 * first thing the team checks and the scanner badge must stay honest.
 */
export function useSecondHomeSummary() {
  return useQuery<SecondHomeSummary>({
    queryKey: secondHomeSummaryQueryKey,
    queryFn: () => api.secondHome.getSummary(),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function useSecondHomeCases(params: ListCasesParams) {
  return useQuery<CaseListResponse>({
    queryKey: secondHomeCaseListQueryKey(params),
    queryFn: () => api.secondHome.listCases(params),
    staleTime: 30 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function useSecondHomeCase(caseId: string | undefined | null) {
  return useQuery<CaseDetail>({
    queryKey: secondHomeCaseQueryKey(caseId ?? ""),
    queryFn: () => api.secondHome.getCase(caseId as string),
    enabled: Boolean(caseId),
    staleTime: 15 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function useCreateSecondHomeCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCaseParams) => api.secondHome.createCase(data),
    onSuccess: (created) => {
      queryClient.setQueryData(
        secondHomeCaseQueryKey(created.case_id),
        created,
      );
      queryClient.invalidateQueries({ queryKey: SECOND_HOME_ROOT_KEY });
    },
  });
}

export function useAdvanceSecondHomeCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AdvanceCaseParams) =>
      api.secondHome.advanceCase(caseId, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(secondHomeCaseQueryKey(caseId), updated);
      queryClient.invalidateQueries({
        queryKey: [...SECOND_HOME_ROOT_KEY, "cases"],
      });
      queryClient.invalidateQueries({ queryKey: secondHomeSummaryQueryKey });
    },
  });
}

export function useAddSecondHomeEvidence(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AddEvidenceParams) =>
      api.secondHome.addEvidence(caseId, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(secondHomeCaseQueryKey(caseId), updated);
    },
  });
}
