export type Difficulty = 'easy' | 'medium' | 'hard'
export type Genre = 'all' | 'horror' | 'comedy' | 'science_fiction' | 'thriller' | 'action' | 'animation' | 'romance' | 'fantasy' | 'adventure'

export interface DifficultyAvailability {
  difficulty: Difficulty
  verified_questions: number
  required_questions: number
  available: boolean
}

export interface QuizAvailability extends DifficultyAvailability {
  genre: Genre
  eligible_films: number
  required_films: number
}

export interface SessionCreated {
  session_id: string
  total_questions: number
}
export interface CustomSessionCreated extends SessionCreated { difficulty: Difficulty; genres: Genre[]; interpretation: string; fallback_used: boolean }

export interface PublicQuestion {
  id: string
  quote: string
  choices: string[]
  question_number: number
  total_questions: number
  score: number
  hint_used: boolean
}

export interface HintResponse {
  question_id: string
  hint: string
  fallback_used: boolean
}
export interface ExplanationResponse { question_id: string; explanation: string; fallback_used: boolean }

export interface AnswerResult {
  question_id: string
  is_correct: boolean
  correct_answer: string
  movie_year: number | null
  score: number
  completed: boolean
}

export interface QuizResults {
  score: number
  total_questions: number
  percentage: number
}

export interface User { id: number; email: string; username: string; created_at: string }
export interface StatsBreakdown { label: string; games_played: number; average_percentage: number; best_percentage: number }
export interface Attempt { genre: string; difficulty: string; score: number; total_questions: number; percentage: number; hints_used: number; completed_at: string }
export interface UserStats {
  games_played: number; average_percentage: number; best_percentage: number
  total_correct: number; total_questions: number; accuracy_percentage: number; hints_used: number
  by_genre: StatsBreakdown[]; by_difficulty: StatsBreakdown[]; recent_attempts: Attempt[]
}
export interface CoachResponse { summary: string; strength: string; improvement: string; recommended_genre: string; recommended_difficulty: string; games_analyzed: number; fallback_used: boolean }
export interface FilmRecommendation { title: string; genres: string[]; reason: string; summary: string; source_url: string | null }
export interface RecommendationsResponse { intro: string; based_on_genres: string[]; recommendations: FilmRecommendation[]; games_analyzed: number; recognized_films_excluded: number; fallback_used: boolean }

