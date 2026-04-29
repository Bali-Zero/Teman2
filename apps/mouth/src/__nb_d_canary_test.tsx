// NB-D canary: synthetic undeclared import. Should fail lint-cross-import.
// PR will be closed without merging.
import type { Foo } from "@nuzantara/totally-fake-nb-d-canary-pkg";
export const X: Foo | null = null;
