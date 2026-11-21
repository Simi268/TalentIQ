export interface Job {
  id: number;
  title: string;
  description?: string;
  requirements?: {
    required_skills?: string[];
    preferred_skills?: string[];
    [key: string]: any;
  };
}

export interface Candidate {
  id: number;
  name: string;
  filename?: string;
  score?: number;
  provisional_score?: number;
  rank?: number;
  score_status?: string;
  evidence_coverage?: number;
  profile?: {
    total_experience_years?: number;
    experience_type?: string;
  };
  explanation?: {
    satisfied?: string[];
    not_verified?: string[];
    missing_skills?: string[];
    required_skill_analysis?: any[];
  };
}