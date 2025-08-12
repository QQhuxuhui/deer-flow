import { parse } from "best-effort-json-parser";

export function parseJSON<T>(json: string | null | undefined, fallback: T) {
  if (!json) {
    return fallback;
  }
  try {
    let raw = json.trim();
    
    // Remove markdown code blocks
    raw = raw
      .replace(/^```json\s*/, "")
      .replace(/^```js\s*/, "")
      .replace(/^```ts\s*/, "")
      .replace(/^```plaintext\s*/, "")
      .replace(/^```\s*/, "")
      .replace(/\s*```$/, "");
    
    // Try to extract JSON from text that might contain extra content
    // Look for JSON objects or arrays in the text
    const jsonMatches = raw.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
    if (jsonMatches && jsonMatches[0]) {
      raw = jsonMatches[0];
    }
    
    // If the content starts with non-JSON text, try to find JSON part
    if (!raw.startsWith('{') && !raw.startsWith('[')) {
      const jsonStart = raw.search(/[{\[]/);
      if (jsonStart > -1) {
        raw = raw.substring(jsonStart);
      }
    }
    
    return parse(raw) as T;
  } catch (error) {
    console.warn('JSON parsing failed:', error, 'Raw content:', json?.substring(0, 200));
    return fallback;
  }
}
