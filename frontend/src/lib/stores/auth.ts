import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import type { TokenResponse } from '$lib/types';

const STORAGE_KEY = 'judo.auth';

export type AuthState = TokenResponse | null;

function load(): AuthState {
	if (!browser) return null;
	const raw = localStorage.getItem(STORAGE_KEY);
	if (!raw) return null;
	try {
		return JSON.parse(raw) as TokenResponse;
	} catch {
		return null;
	}
}

export const auth = writable<AuthState>(load());

auth.subscribe((value) => {
	if (!browser) return;
	if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
	else localStorage.removeItem(STORAGE_KEY);
});

export function setAuth(token: TokenResponse) {
	auth.set(token);
}

export function logout() {
	auth.set(null);
}

export function getToken(): string | null {
	const state = load();
	return state?.access_token ?? null;
}
