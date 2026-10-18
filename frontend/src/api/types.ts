// Типы строго по контракту API v1 (FRONTEND_TASK.md).

export type Role = 'employee' | 'manager' | 'hr';

export interface Profile {
  id: number;
  name: string;
  email: string;
  role: Role;
  company: string;
  position: string;
  department: string;
  manager_id: number | null;
  manager_name: string | null;
  hire_date: string;
  vacation_balance: number;
  branch_id?: string | null;
  branch_address?: string | null;
}

export interface AuthResponse {
  user: Profile;
  csrf_token: string;
}

export interface Health {
  status: string;
  service: string;
  version: string;
  assistant_mode: string;
}

export type RequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';

export interface HrRequest {
  id: number;
  user_id: number;
  employee_name: string;
  department: string;
  type: 'vacation';
  start_date: string;
  end_date: string;
  days: number;
  comment: string;
  status: RequestStatus;
  created_at: string;
  updated_at: string;
  reviewer_id: number | null;
  reviewer_name: string | null;
  decision_comment: string | null;
}

export interface HistoryItem {
  id: number;
  status: RequestStatus;
  actor_id: number;
  actor_name: string;
  comment: string;
  created_at: string;
}

export interface HrRequestDetails extends HrRequest {
  history: HistoryItem[];
}

export type RequestScope = 'mine' | 'team' | 'all';

export interface CreateRequestBody {
  type: 'vacation';
  start_date: string;
  end_date: string;
  comment: string;
}

export type CourseStatus = 'assigned' | 'in_progress' | 'completed';

export interface CourseSummary {
  id: number;
  title: string;
  description: string;
  duration_minutes: number;
  progress: number;
  status: CourseStatus;
  assigned_at: string;
  completed_at: string | null;
  score: number | null;
  lesson_count: number;
  completed_lessons: number;
}

export interface Lesson {
  id: number;
  title: string;
  content: string;
  completed: boolean;
}

export interface CourseDetails {
  course: CourseSummary;
  lessons: Lesson[];
  quiz: { question: string; options: string[] };
}

export interface QuizResult {
  passed: boolean;
  score: number;
  course: CourseSummary;
}

export interface CatalogCourse {
  id: number;
  title: string;
  description: string;
  duration_minutes: number;
}

export interface Dashboard {
  profile: Profile;
  stats: {
    my_pending: number;
    unread_notifications: number;
    assigned_courses: number;
    completed_courses: number;
    pending_approvals: number;
  };
  recent_requests: HrRequest[];
  courses: CourseSummary[];
}

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  body: string;
  entity_type: 'request' | 'course' | string;
  entity_id: number;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  items: AppNotification[];
  unread_count: number;
}

export interface AssistantSource {
  id: number;
  title: string;
  url: string;
}

export interface AssistantAnswer {
  answer: string;
  found: boolean;
  mode: 'extractive' | 'grounded_llm' | 'conversation';
  sources: AssistantSource[];
  notice?: string;
}

export interface KnowledgeSummary {
  id: number;
  title: string;
  summary: string;
}

export interface KnowledgeDoc {
  id: number;
  title: string;
  content: string;
  summary?: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface SetupStatus { setup_required: boolean; demo_mode: boolean }
export interface SetupBody { name: string; email: string; password: string; company: string }
export interface NewEmployee extends SetupBody {
  role: Role; position: string; department: string; manager_id: number | null; hire_date: string; vacation_balance: number;
}
export interface ArticleBody { title: string; summary: string; content: string; roles: Role[]; is_active: boolean }
export interface AdminArticle extends ArticleBody { id: number; updated_at: string | null }
export interface CourseBody {
  title: string; description: string; duration_minutes: number; lessons: {title: string; content: string}[];
  question: string; options: string[]; correct_index: number;
}
export interface AdminCourse extends CourseBody { id: number; assignment_count: number }
export interface AssistantStatus { mode: 'extractive' | 'grounded_llm'; model_enabled: boolean; provider: string; model?: string; note: string }
export interface LearningPackSummary { title: string; disclaimer: string; documents_count: number; courses_count: number; imported_documents: number; imported_courses: number }
export interface LearningPackResult { created_documents: number; created_courses: number; skipped_documents: number; skipped_courses: number }
