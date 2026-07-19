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
