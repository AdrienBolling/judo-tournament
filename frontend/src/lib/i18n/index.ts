import { derived, writable } from 'svelte/store';
import { browser } from '$app/environment';
import { messages, type Locale } from './messages';

export { LOCALES, type Locale } from './messages';

const STORAGE_KEY = 'judo.locale';
const DEFAULT_LOCALE: Locale = 'fr';

function initial(): Locale {
	if (!browser) return DEFAULT_LOCALE;
	const saved = localStorage.getItem(STORAGE_KEY);
	return saved === 'en' || saved === 'fr' ? saved : DEFAULT_LOCALE;
}

/** Active UI language. Defaults to French; persisted to localStorage. */
export const locale = writable<Locale>(initial());

locale.subscribe((value) => {
	if (browser) {
		localStorage.setItem(STORAGE_KEY, value);
		document.documentElement.lang = value;
	}
});

export function setLocale(value: Locale) {
	locale.set(value);
}

type Params = Record<string, string | number>;

/**
 * Reactive translator. Use as `$t('some.key')` in components, optionally with
 * interpolation params: `$t('detail.maxGroupSize', { n: 4 })`.
 * Falls back to the French string, then to the raw key, if a key is missing.
 */
export const t = derived(locale, ($locale) => {
	return (key: string, params?: Params): string => {
		let str = messages[$locale][key] ?? messages[DEFAULT_LOCALE][key] ?? key;
		if (params) {
			for (const [k, v] of Object.entries(params)) {
				str = str.replaceAll(`{${k}}`, String(v));
			}
		}
		return str;
	};
});
