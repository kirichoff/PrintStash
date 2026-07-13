import { describe, expect, it } from "vitest";

import { normalizeRecommendedGcodeFiles } from "../presentation";

describe("normalizeRecommendedGcodeFiles", () => {
  it("shows only newest G-code revision as recommended when legacy data contains duplicates", () => {
    const files = normalizeRecommendedGcodeFiles([
      { id: 1, file_type: "gcode" as const, version: 1, is_recommended: true },
      { id: 2, file_type: "gcode" as const, version: 2, is_recommended: true },
      { id: 3, file_type: "gcode" as const, version: 3, is_recommended: false },
      { id: 4, file_type: "stl" as const, version: 1, is_recommended: true },
    ]);

    expect(files.map((file) => file.is_recommended)).toEqual([false, true, false, true]);
  });
});
