export type Role = 'admin' | 'coach' | 'referee' | 'inscription';

export interface TokenResponse {
	access_token: string;
	token_type: string;
	role: Role;
	display_name: string;
	club_id: string | null;
	tournament_id: string | null;
}

export interface Club {
	id: string;
	name: string;
	location: string;
}

export interface Coach {
	id: string;
	first_name: string;
	last_name: string;
	email: string;
	phone_number: string;
	club_id: string;
}

export interface Member {
	id: string;
	first_name: string;
	last_name: string;
	date_of_birth: string | null;
	weight: number | null;
	gender: string;
	club_id: string;
	age: number | null;
	age_category: string;
	weight_updated_at: string | null;
	is_complete: boolean;
}

export interface Tournament {
	id: string;
	name: string;
	date: string;
	location: string;
	hosting_club_id: string;
	status: string; // "open" | "closed"
	reweigh_months: number;
}

export interface PublicTournament {
	id: string;
	name: string;
	date: string;
	location: string;
}

export interface Participant {
	id: string;
	member_id: string;
	tournament_id: string;
	group_id: string | null;
	member_name: string;
	gender: string;
	weight: number | null;
	age_category: string;
	club_id: string | null;
	group_name: string | null;
}

export interface Group {
	id: string;
	name: string;
	tournament_id: string;
	participants: Participant[];
}

export interface Match {
	id: string;
	group_id: string;
	participant_a_id: string;
	participant_b_id: string;
	name_a: string;
	name_b: string;
	winner_id: string | null;
	score_a_ippon: number;
	score_a_wazari: number;
	score_a_yuko: number;
	score_b_ippon: number;
	score_b_wazari: number;
	score_b_yuko: number;
	completed: boolean;
}

export interface StandingRow {
	participant_id: string;
	name: string;
	wins: number;
	draws: number;
	losses: number;
	points: number;
}

export interface RefereeToken {
	id: string;
	token: string;
	label: string;
	tournament_id: string;
	role: string; // "referee" | "inscription"
}

export interface RegistrationRow {
	member_id: string;
	member_name: string;
	first_name: string;
	last_name: string;
	club_name: string;
	gender: string;
	weight: number | null;
	registered: boolean;
	weight_updated_at: string | null;
	weight_stale: boolean;
}

export interface MemberResult {
	member_id: string;
	member_name: string;
	group_label: string;
	wins: number;
	draws: number;
	losses: number;
	rank: number | null;
	group_size: number | null;
}

export interface TournamentResult {
	tournament_id: string;
	tournament_name: string;
	date: string;
	members: MemberResult[];
}

export interface ClubResults {
	total_wins: number;
	total_draws: number;
	total_losses: number;
	tournaments: TournamentResult[];
}
