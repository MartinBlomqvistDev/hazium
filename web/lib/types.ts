export interface Landmark {
  name: string;
  cas: string;
  note: string;
  action_date: string;
  flagged: boolean;
  lead_time_months: {
    "10": number | null;
    "20": number | null;
    "50": number | null;
  };
}

export interface AggregatePoint {
  cutoff: string;
  xgboost_ap: number;
  best_trivial_ap: number;
}

export type MarkerType = "media" | "regulator" | "ban";

export interface CapabilityMarker {
  type: MarkerType;
  date: string;
  precision: "day" | "month" | "year";
  label: string;
  source: string;
  url: string;
}

export type CapabilityOutcome =
  | "clean_lead"
  | "ahead_of_eu_action"
  | "level"
  | "behind"
  | "miss"
  | "data_issue";

export interface CapabilityLandmark {
  name: string;
  cas: string;
  hazard: string;
  outcome: CapabilityOutcome;
  /** True for the held-out north-star (fluazinam), which is not one of the ten benchmark EU bans. */
  held_out?: boolean;
  hazium_flag: {
    date: string;
    rank: number;
    k: number;
    lower_bound: boolean;
  } | null;
  markers: CapabilityMarker[];
  note: string;
}

export interface CapabilityData {
  k_primary: number;
  note: string;
  outcomes: Record<string, string>;
  landmarks: CapabilityLandmark[];
}

export interface TrajectoryPoint {
  year: number;
  rank: number;
  population: number;
}

export interface SubstanceDetail {
  use: string;
  trajectory: TrajectoryPoint[];
}

export type SubstanceDetailMap = Record<string, SubstanceDetail>;

export interface RankRaceRow {
  cas: string;
  name: string;
  score: number;
  rank: number;
  banned_year: number | null;
}

export interface RankRaceData {
  years: number[];
  top_n: number;
  per_year: Record<string, RankRaceRow[]>;
}

export interface HewbData {
  hewb_version: string;
  provisional: boolean;
  provisional_note: string;
  headline: {
    landmarks_flagged: number;
    landmarks_total: number;
    best_lead_time_months: number | null;
    best_lead_time_case: string | null;
  };
  landmarks: Landmark[];
  aggregate: AggregatePoint[];
}
