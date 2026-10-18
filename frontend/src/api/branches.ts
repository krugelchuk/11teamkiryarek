import { get, patch } from './client';
import type { Profile, CourseSummary, HrRequest } from './types';

export interface Branch {
  id: string; name: string; address: string; district: string; lat: number; lon: number;
  source_url: string; checked_at: string; min_staff: number | null;
  member_count: number; min_remaining: number; max_approved: number; max_pending: number;
  shortage_days: number; is_mine: boolean;
}
export interface BranchList {
  items: Branch[]; from: string; to: string; scope: string; demo_mode: boolean; notice: string; source_url: string;
}
export interface BranchMember { id: number; name: string; role: Profile['role']; position: string; department: string; branch_id: string }
export interface BranchLeave { id: number; user_id: number; start_date: string; end_date: string; status: 'pending' | 'approved' }
export interface CoverageDay { date: string; approved: number; pending: number; remaining: number; shortage: boolean }
export interface BranchDetail {
  branch: Branch; members: BranchMember[]; leaves: BranchLeave[]; days: string[]; calendar: CoverageDay[]; scope: string;
}
export interface BranchEmployee { profile: Profile; courses: CourseSummary[]; requests: HrRequest[] }
const range = (from: string, to: string) => new URLSearchParams({from, to}).toString();
export const branchApi = {
  list: (from: string, to: string) => get<BranchList>(`/api/branches?${range(from, to)}`),
  detail: (id: string, from: string, to: string) => get<BranchDetail>(`/api/branches/${id}?${range(from, to)}`),
  employee: (id: string, uid: number) => get<BranchEmployee>(`/api/branches/${id}/employees/${uid}`),
  assign: (uid: number, branch_id: string | null) => patch<Profile>(`/api/admin/users/${uid}/branch`, {branch_id}),
  configure: (id: string, min_staff: number | null) => patch<{ok: boolean}>(`/api/admin/branches/${id}`, {min_staff}),
};
