import { getToken, logout } from '$lib/stores/auth';
import { goto } from '$app/navigation';
import type {
	Club,
	ClubResults,
	Coach,
	Group,
	Match,
	Member,
	Participant,
	PublicTournament,
	RefereeToken,
	RegistrationRow,
	StandingRow,
	TokenResponse,
	Tournament
} from '$lib/types';

const BASE = '/api';

export class ApiError extends Error {
	status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const headers: Record<string, string> = {};
	const token = getToken();
	if (token) headers['Authorization'] = `Bearer ${token}`;

	let payload: BodyInit | undefined;
	if (body instanceof FormData) {
		payload = body;
	} else if (body !== undefined) {
		headers['Content-Type'] = 'application/json';
		payload = JSON.stringify(body);
	}

	const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });

	if (res.status === 401) {
		logout();
		goto('/login');
		throw new ApiError(401, 'Session expired — please log in again.');
	}

	if (!res.ok) {
		let detail = `Request failed (${res.status})`;
		try {
			const data = await res.json();
			if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : detail;
		} catch {
			/* ignore */
		}
		throw new ApiError(res.status, detail);
	}

	if (res.status === 204) return undefined as T;
	return (await res.json()) as T;
}

/** Fetch a binary response (e.g. a PDF) with auth, returning a Blob. */
async function requestBlob(path: string): Promise<Blob> {
	const token = getToken();
	const res = await fetch(`${BASE}${path}`, {
		headers: token ? { Authorization: `Bearer ${token}` } : {}
	});
	if (res.status === 401) {
		logout();
		goto('/login');
		throw new ApiError(401, 'Session expired — please log in again.');
	}
	if (!res.ok) throw new ApiError(res.status, `Download failed (${res.status})`);
	return res.blob();
}

export const api = {
	// auth + setup
	setupStatus: () => request<{ needs_setup: boolean }>('GET', '/setup/status'),
	setupAdmin: (username: string, password: string) =>
		request<TokenResponse>('POST', '/setup/admin', { username, password }),
	loginAdmin: (username: string, password: string) =>
		request<TokenResponse>('POST', '/auth/login/admin', { username, password }),
	loginCoach: (email: string, password: string) =>
		request<TokenResponse>('POST', '/auth/login/coach', { email, password }),
	loginReferee: (token: string, tournamentId?: string) =>
		request<TokenResponse>('POST', '/auth/login/referee', {
			token,
			tournament_id: tournamentId ?? null
		}),
	loginInscription: (token: string, tournamentId?: string) =>
		request<TokenResponse>('POST', '/auth/login/inscription', {
			token,
			tournament_id: tournamentId ?? null
		}),
	openTournaments: () => request<PublicTournament[]>('GET', '/public/open-tournaments'),

	// clubs / coaches / members
	listClubs: () => request<Club[]>('GET', '/clubs'),
	createClub: (name: string, location: string) =>
		request<Club>('POST', '/clubs', { name, location }),
	listCoaches: (clubId: string) => request<Coach[]>('GET', `/clubs/${clubId}/coaches`),
	createCoach: (clubId: string, data: Omit<Coach, 'id' | 'club_id'> & { password: string }) =>
		request<Coach>('POST', `/clubs/${clubId}/coaches`, data),
	deleteCoach: (coachId: string) => request<void>('DELETE', `/coaches/${coachId}`),
	listMembers: (clubId: string) => request<Member[]>('GET', `/clubs/${clubId}/members`),
	createMember: (
		clubId: string,
		data: {
			first_name: string;
			last_name: string;
			gender: string;
			date_of_birth?: string | null;
			weight?: number | null;
		}
	) => request<Member>('POST', `/clubs/${clubId}/members`, data),
	updateMember: (
		memberId: string,
		data: {
			first_name?: string;
			last_name?: string;
			date_of_birth?: string;
			weight?: number;
			gender?: string;
		}
	) => request<Member>('PATCH', `/members/${memberId}`, data),
	importMembers: (clubId: string, file: File) => {
		const fd = new FormData();
		fd.append('file', file);
		return request<Member[]>('POST', `/clubs/${clubId}/members/import`, fd);
	},

	// tournaments
	listTournaments: () => request<Tournament[]>('GET', '/tournaments'),
	getTournament: (tid: string) => request<Tournament>('GET', `/tournaments/${tid}`),
	createTournament: (data: {
		name: string;
		date: string;
		location: string;
		hosting_club_id: string;
	}) => request<Tournament>('POST', '/tournaments', data),
	setTournamentStatus: (tid: string, status: 'open' | 'closed') =>
		request<Tournament>('PATCH', `/tournaments/${tid}/status`, { status }),
	setTournamentSettings: (tid: string, reweighMonths: number) =>
		request<Tournament>('PATCH', `/tournaments/${tid}/settings`, { reweigh_months: reweighMonths }),
	listParticipants: (tid: string) =>
		request<Participant[]>('GET', `/tournaments/${tid}/participants`),
	registerParticipants: (tid: string, memberIds: string[]) =>
		request<Participant[]>('POST', `/tournaments/${tid}/participants`, { member_ids: memberIds }),
	registrationList: (tid: string) =>
		request<RegistrationRow[]>('GET', `/tournaments/${tid}/registration`),
	unregisterParticipant: (tid: string, memberId: string) =>
		request<void>('DELETE', `/tournaments/${tid}/participants/by-member/${memberId}`),
	listGroups: (tid: string) => request<Group[]>('GET', `/tournaments/${tid}/groups`),
	generateGroups: (tid: string, maxGroupSize: number, maxAdditionalGroups: number) =>
		request<Group[]>('POST', `/tournaments/${tid}/groups/generate`, {
			max_group_size: maxGroupSize,
			max_additional_groups: maxAdditionalGroups
		}),
	setGroupParticipants: (tid: string, groupId: string, participantIds: string[]) =>
		request<Group[]>('PUT', `/tournaments/${tid}/groups/${groupId}/participants`, {
			participant_ids: participantIds
		}),
	participantsPdf: (tid: string, query: string) =>
		requestBlob(`/tournaments/${tid}/participants.pdf${query}`),

	// referee tokens
	listTokens: (tid: string) => request<RefereeToken[]>('GET', `/tournaments/${tid}/tokens`),
	createToken: (tid: string, data: { label: string; role?: string; token?: string }) =>
		request<RefereeToken>('POST', `/tournaments/${tid}/tokens`, data),
	updateToken: (tid: string, tokenId: string, data: { token?: string; label?: string }) =>
		request<RefereeToken>('PUT', `/tournaments/${tid}/tokens/${tokenId}`, data),

	// matches
	listMatches: (groupId: string) => request<Match[]>('GET', `/groups/${groupId}/matches`),
	standings: (groupId: string) => request<StandingRow[]>('GET', `/groups/${groupId}/standings`),
	score: (matchId: string, side: 'a' | 'b', point: 'ippon' | 'wazari' | 'yuko') =>
		request<Match>('POST', `/matches/${matchId}/score`, { side, point }),
	endMatch: (matchId: string) => request<Match>('POST', `/matches/${matchId}/end`),
	resetMatch: (matchId: string) => request<Match>('POST', `/matches/${matchId}/reset`),

	// results
	clubResults: (clubId: string) => request<ClubResults>('GET', `/clubs/${clubId}/results`)
};
