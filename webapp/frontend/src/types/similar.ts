import type { Measure } from "./measure";

export interface SimilarResult {
    score: number;
    label: "Identical" | "Similar" | "Different";
    measure: Measure;
}
