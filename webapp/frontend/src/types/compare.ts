import type { Measure, WindowSpec } from "./measure";

export interface LeafSource {
    table: string;
    column: string;
}

export interface ExprComparison {
    raw_a: string;
    raw_b: string;
    normalized_a: string;
    normalized_b: string;
    same: boolean;
}

export interface WindowFieldDiff {
    spec_index: number;
    field: string;
    value_a: string | null;
    value_b: string | null;
}

export interface WindowComparison {
    specs_a: WindowSpec[];
    specs_b: WindowSpec[];
    same: boolean;
    field_diffs: WindowFieldDiff[];
}

export interface LineageComparison {
    leaf_sources_a: LeafSource[];
    leaf_sources_b: LeafSource[];
    shared_leaves: LeafSource[];
    only_in_a: LeafSource[];
    only_in_b: LeafSource[];
    leaves_same: boolean;
    has_extra_hops_a: boolean;
    has_extra_hops_b: boolean;
}

export interface PairComparison {
    id_a: string;
    id_b: string;
    view_a: string;
    view_b: string;
    name_a: string;
    name_b: string;
    score: number;
    label: "Identical" | "Similar" | "Different";
    expr: ExprComparison;
    window: WindowComparison;
    lineage: LineageComparison;
}

export interface CompareResult {
    measures: Measure[];
    pairs: PairComparison[];
}
