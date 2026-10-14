<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import { t } from '$lib/i18n';
	import type { Club, ClubResults, MemberResult } from '$lib/types';

	const resultCols = $derived<Column<MemberResult>[]>([
		{ key: 'member_name', label: $t('results.member') },
		{ key: 'group_label', label: $t('common.group') },
		{ key: 'wins', label: $t('results.w'), numeric: true },
		{ key: 'draws', label: $t('results.d'), numeric: true },
		{ key: 'losses', label: $t('results.l'), numeric: true },
		{
			key: 'rank',
			label: $t('results.rank'),
			numeric: true,
			format: (m) => (m.rank ? `${m.rank} / ${m.group_size}` : '—'),
			sortValue: (m) => m.rank ?? Number.MAX_SAFE_INTEGER
		}
	]);

	let clubs = $state<Club[]>([]);
	let clubId = $state('');
	let results = $state<ClubResults | null>(null);
	let error = $state('');
	const isAdmin = $derived($auth?.role === 'admin');
	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	onMount(async () => {
		if ($auth?.role === 'coach' && $auth.club_id) {
			clubId = $auth.club_id;
		} else {
			try {
				clubs = await api.listClubs();
				if (clubs.length) clubId = clubs[0].id;
			} catch (e) {
				error = msg(e);
			}
		}
	});

	$effect(() => {
		if (clubId) load(clubId);
	});

	async function load(id: string) {
		error = '';
		try {
			results = await api.clubResults(id);
		} catch (e) {
			error = msg(e);
		}
	}
</script>

<h1>{$t('results.title')}</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if isAdmin}
	<div class="field" style="max-width:360px">
		<label for="club">{$t('results.selectClub')}</label>
		<select id="club" bind:value={clubId}>
			{#each clubs as c}<option value={c.id}>{c.name}</option>{/each}
		</select>
	</div>
{/if}

{#if results}
	{#if results.tournaments.length === 0}
		<p class="muted">{$t('results.noParticipation')}</p>
	{:else}
		{#each results.tournaments as tour}
			<div class="card">
				<h2>
					{tour.tournament_name}
					<span class="muted" style="font-weight:400">— {tour.date}</span>
				</h2>
				<DataTable columns={resultCols} rows={tour.members} />
			</div>
		{/each}

		<div class="card totals">
			<div><div class="big">{results.total_wins}</div><div class="muted">{$t('results.wins')}</div></div>
			<div><div class="big">{results.total_draws}</div><div class="muted">{$t('results.draws')}</div></div>
			<div><div class="big">{results.total_losses}</div><div class="muted">{$t('results.losses')}</div></div>
		</div>
	{/if}
{/if}

<style>
	.totals {
		display: flex;
		gap: 2rem;
		text-align: center;
	}
	.big {
		font-size: 2rem;
		font-weight: 700;
	}
</style>
