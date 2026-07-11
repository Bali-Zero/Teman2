declare module "gray-matter" {
  export interface GrayMatterFile<I = string> {
    data: Record<string, any>;
    content: string;
    excerpt?: string;
    orig: I;
    language: string;
    matter: string;
    stringify(language?: string): string;
  }

  export default function matter<I = string>(
    input: I,
    options?: Record<string, unknown>,
  ): GrayMatterFile<I>;
}
