<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import ScoringPanel from '$lib/components/ScoringPanel.svelte';
	import { t } from '$lib/i18n';
	import type { Tournament } from '$lib/types';

	// Referees are locked to the tournament their token granted.
	const tournamentId = $derived($auth?.tournament_id ?? '');
	let tournament = $state<Tournament | null>(null);
	let error = $state('');
	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	onMount(async () => {
		if (!tournamentId) return;
		try {
			tournament = await api.getTournament(tournamentId);
		} catch (e) {
			error = msg(e);
		}
	});
</script>

<h1>{$t('referee.title')}</h1>
{#if tournament}<h2>{tournament.name}</h2>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if tournamentId}
	<ScoringPanel {tournamentId} />
{:else}
	<p class="muted">{$t('referee.noTournaments')}</p>
{/if}
