/** Dependency-free client. All dates are YYYY-MM-DD; all IDs are numbers. */
export class HRApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "HRApiError";
    this.status = status;
    this.code = code;
  }
}

export function createHRClient(baseURL = "http://localhost:8000") {
  const base = baseURL.replace(/\/$/, "");
  let csrf = "";
  async function request(method, path, body) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;
    const response = await fetch(base + path, {
      method, headers, credentials: "include",
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) csrf = "";
      throw new HRApiError(response.status, data.error?.code || "request_failed", data.error?.message || "Ошибка запроса");
    }
    return data;
  }
  return {
    async login(email, password) {
      const data = await request("POST", "/api/auth/login", { email, password });
      csrf = data.csrf_token;
      return data.user;
    },
    async restore() {
      const data = await request("GET", "/api/auth/me");
      csrf = data.csrf_token;
      return data.user;
    },
    async logout() {
      const data = await request("POST", "/api/auth/logout", {});
      csrf = "";
      return data;
    },
    profile: () => request("GET", "/api/profile"),
    dashboard: () => request("GET", "/api/dashboard"),
    team: () => request("GET", "/api/team"),
    requests: (scope = "mine") => request("GET", "/api/requests?scope=" + encodeURIComponent(scope)),
    requestDetails: (id) => request("GET", `/api/requests/${id}`),
    createVacation: (start_date, end_date, comment = "") => request("POST", "/api/requests", { type: "vacation", start_date, end_date, comment }),
    decide: (id, decision, comment = "") => request("POST", `/api/requests/${id}/decision`, { decision, comment }),
    cancel: (id, comment = "") => request("POST", `/api/requests/${id}/cancel`, { comment }),
    notifications: () => request("GET", "/api/notifications"),
    markRead: (id) => request("PATCH", `/api/notifications/${id}/read`, {}),
    markAllRead: () => request("POST", "/api/notifications/read-all", {}),
    courses: () => request("GET", "/api/courses"),
    courseDetails: (id) => request("GET", `/api/courses/${id}`),
    completeLesson: (courseId, lessonId) => request("POST", `/api/courses/${courseId}/lessons/${lessonId}/complete`, {}),
    submitQuiz: (courseId, answer_index) => request("POST", `/api/courses/${courseId}/quiz`, { answer_index }),
    courseCatalog: () => request("GET", "/api/admin/courses"),
    assignCourse: (user_id, course_id) => request("POST", "/api/admin/assignments", { user_id, course_id }),
    ask: (question) => request("POST", "/api/assistant/ask", { question }),
    knowledge: () => request("GET", "/api/knowledge"),
    article: (id) => request("GET", `/api/knowledge/${id}`),
    request,
  };
}
