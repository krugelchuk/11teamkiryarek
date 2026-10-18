import { get, patch, post, setCsrfToken } from './client';
export { branchApi } from './branches';
export { integrationApi } from './integrations';
import type { SetupStatus, SetupBody, NewEmployee, ArticleBody, AdminArticle, CourseBody, AdminCourse, AssistantStatus, LearningPackSummary, LearningPackResult } from './types';
import type {
  AppNotification,
  AssistantAnswer,
  AuthResponse,
  CatalogCourse,
  CourseDetails,
  CourseSummary,
  CreateRequestBody,
  Dashboard,
  Health,
  HrRequest,
  HrRequestDetails,
  KnowledgeDoc,
  KnowledgeSummary,
  NotificationsResponse,
  Profile,
  QuizResult,
  RequestScope,
} from './types';

// Все вызовы API в одном месте — здесь же делается адаптация, если контракт сдвинется.

export const api = {
  assistantStatus: () => get<AssistantStatus>('/api/assistant/status'),
  learningPack: () => get<LearningPackSummary>('/api/admin/learning-pack'),
  importLearningPack: () => post<LearningPackResult>('/api/admin/learning-pack/import', {}),
  setupStatus: () => get<SetupStatus>('/api/setup/status'),
  setup: (body: SetupBody) => post<{ok: boolean}>('/api/setup', body),
  createEmployee: (body: NewEmployee) => post<Profile>('/api/admin/users', body),
  adminArticles: () => get<{items: AdminArticle[]}>('/api/admin/knowledge'),
  saveArticle: (body: ArticleBody, id?: number) => id ? patch<AdminArticle>(`/api/admin/knowledge/${id}`, body) : post<AdminArticle>('/api/admin/knowledge', body),
  adminCourseDetails: () => get<{items: AdminCourse[]}>('/api/admin/courses'),
  saveCourse: (body: CourseBody, id?: number) => id ? patch<AdminCourse>(`/api/admin/courses/${id}`, body) : post<AdminCourse>('/api/admin/courses', body),
  health: () => get<Health>('/api/health'),

  async login(email: string, password: string) {
    const r = await post<AuthResponse>('/api/auth/login', { email, password }, { silent401: true });
    setCsrfToken(r.csrf_token);
    return r;
  },
  async me() {
    const r = await get<AuthResponse>('/api/auth/me', { silent401: true });
    setCsrfToken(r.csrf_token);
    return r;
  },
  async logout() {
    const result = await post<{ ok: boolean }>('/api/auth/logout', {}, { silent401: true });
    setCsrfToken(null);
    return result;
  },

  profile: () => get<Profile>('/api/profile'),
  dashboard: () => get<Dashboard>('/api/dashboard'),
  team: () => get<{ items: Profile[] }>('/api/team'),

  requests: (scope: RequestScope = 'mine') => get<{ items: HrRequest[] }>(`/api/requests?scope=${scope}`),
  createRequest: (body: CreateRequestBody) => post<HrRequest>('/api/requests', body),
  request: (id: number) => get<HrRequestDetails>(`/api/requests/${id}`),
  decide: (id: number, decision: 'approved' | 'rejected', comment: string) =>
    post<HrRequest>(`/api/requests/${id}/decision`, { decision, comment }),
  cancel: (id: number, comment?: string) =>
    post<HrRequest>(`/api/requests/${id}/cancel`, comment ? { comment } : {}),

  notifications: () => get<NotificationsResponse>('/api/notifications'),
  markRead: (id: number) => patch<AppNotification>(`/api/notifications/${id}/read`, {}),
  markAllRead: () => post<{ ok: boolean }>('/api/notifications/read-all', {}),

  courses: () => get<{ items: CourseSummary[] }>('/api/courses'),
  course: (id: number) => get<CourseDetails>(`/api/courses/${id}`),
  completeLesson: (courseId: number, lessonId: number) =>
    post<CourseSummary>(`/api/courses/${courseId}/lessons/${lessonId}/complete`, {}),
  submitQuiz: (courseId: number, answerIndex: number) =>
    post<QuizResult>(`/api/courses/${courseId}/quiz`, { answer_index: answerIndex }),
  adminCourses: () => get<{ items: CatalogCourse[] }>('/api/admin/courses'),
  assignCourse: (userId: number, courseId: number) =>
    post<{ ok: boolean }>('/api/admin/assignments', { user_id: userId, course_id: courseId }),

  ask: (question: string) => post<AssistantAnswer>('/api/assistant/ask', { question }),
  knowledge: () => get<{ items: KnowledgeSummary[] }>('/api/knowledge'),
  /** path — относительный url источника ("/api/knowledge/{id}") или id документа */
  knowledgeDoc: (idOrUrl: number | string) =>
    get<KnowledgeDoc>(typeof idOrUrl === 'number' ? `/api/knowledge/${idOrUrl}` : idOrUrl),
  async sourceDoc(url: string): Promise<KnowledgeDoc> {
    if (url === '/api/profile') {
      const profile = await get<Profile>('/api/profile');
      return {
        id: profile.id,
        title: 'Мой профиль',
        content: `Сотрудник: ${profile.name}\nДолжность: ${profile.position}\nПодразделение: ${profile.department}\nРуководитель: ${profile.manager_name ?? '—'}\nДата приёма: ${profile.hire_date}\nДоступно дней отпуска: ${profile.vacation_balance}\n\nИсточник: ваш текущий профиль. Кадровые данные доступны только для чтения.`,
      };
    }
    if (!/^\/api\/knowledge\/[1-9]\d*$/.test(url)) throw new Error('Неизвестный источник ответа');
    return get<KnowledgeDoc>(url);
  },
};
