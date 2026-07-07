# TKA KBLI Correlation Dataset Plan

## Goal

Build a source-traceable draft dataset for KBLI 2025 codes and TKA position rules without ingesting any permitted jabatan that lacks a verified Kepmenaker lampiran row.

## Steps

1. Verify KBLI source shape and count.
2. Verify the regulatory model from PP 34/2021 and the TKA article.
3. Identify current positive-list and closed-list instruments through JDIH Kemnaker.
4. Generate conservative dataset:
   - all 1559 KBLI codes present;
   - global forbidden list from Kepmenaker 349/2019;
   - no permitted positions until Kepmenaker 228/2019 lampiran rows are downloaded and extracted;
   - LOW confidence for all records.
5. Emit validation and verification reports.

## Constraint

The Air-M5 sandbox cannot reach Pro/Ollama and cannot download the Kepmenaker 228 PDF via shell. Do not infer any permitted jabatan from generated guides or proxy mappings.
