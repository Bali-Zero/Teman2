/**
 * SchemaInjector - Generic JSON-LD Schema Injector
 *
 * Accepts an array of schema objects and renders them as JSON-LD scripts.
 * Used for Semantic Web optimization and LLM-friendly structured data.
 *
 * IMPORTANT: Uses native <script> tag instead of Next.js Script component
 * to ensure JSON-LD is present in the static HTML for Googlebot.
 *
 * @param schemas - Array of schema objects to inject as JSON-LD
 */
export function SchemaInjector({
  schemas,
}: {
  readonly schemas: readonly any[];
}) {
  return (
    <>
      {schemas.map((schema, index) => {
        // Generate unique ID based on schema type
        const schemaType = schema["@type"] || "schema";
        const uniqueId = `${schemaType.toLowerCase()}-${index}`;

        return (
          <script
            key={uniqueId}
            id={`json-ld-${uniqueId}`}
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
          />
        );
      })}
    </>
  );
}
