<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { get } from 'svelte/store';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import { t } from '$lib/i18n';
	import type { Group, Match, StandingRow } from '$lib/types';

	let { tournamentId }: { tournamentId: string } = $props();

	// '#' reflects the standings position (points order) and stays fixed even
	// when the user sorts by another column.
	const standingCols = $derived<Column[]>([
		{ key: 'rank', label: '#', numeric: true },
		{ key: 'name', label: $t('common.name') },
		{ key: 'wins', label: $t('results.w'), numeric: true },
		{ key: 'draws', label: $t('results.d'), numeric: true },
		{ key: 'losses', label: $t('results.l'), numeric: true },
		{ key: 'points', label: $t('referee.pts'), numeric: true }
	]);

	let groups = $state<Group[]>([]);
	let groupId = $state('');
	let matches = $state<Match[]>([]);
	let standings = $state<StandingRow[]>([]);
	let error = $state('');
	let busy = $state(false);

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	// Reload whenever the tournament changes.
	$effect(() => {
		if (tournamentId) loadGroups(tournamentId);
	});
	$effect(() => {
		if (groupId) loadGroup(groupId);
	});

	async function loadGroups(tid: string) {
		error = '';
		try {
			groups = await api.listGroups(tid);
			groupId = groups.length ? groups[0].id : '';
			if (!groups.length) {
				matches = [];
				standings = [];
			}
		} catch (e) {
			error = msg(e);
		}
	}

	async function loadGroup(gid: string) {
		error = '';
		try {
			[matches, standings] = await Promise.all([api.listMatches(gid), api.standings(gid)]);
		} catch (e) {
			error = msg(e);
		}
	}

	function winnerName(m: Match): string {
		if (m.winner_id === m.participant_a_id) return m.name_a;
		if (m.winner_id === m.participant_b_id) return m.name_b;
		return '';
	}

	async function act(fn: () => Promise<Match>) {
		busy = true;
		error = '';
		try {
			await fn();
			if (groupId) await loadGroup(groupId);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	const standingRows = $derived(standings.map((s, i) => ({ ...s, rank: i + 1 })));
</script>

{#if error}<p class="error">{error}</p>{/if}

{#if groups.length === 0}
	<p class="muted">{$t('referee.noGroups')}</p>
{:else}
	<div class="field" style="max-width:320px">
		<label for="g">{$t('referee.selectGroup')}</label>
		<select id="g" bind:value={groupId}>
			{#each groups as g}<option value={g.id}>{g.name}</option>{/each}
		</select>
	</div>

	{#if standings.length}
		<div class="card">
			<h3>{$t('referee.standings')}</h3>
			<DataTable columns={standingCols} rows={standingRows} />
		</div>
	{/if}

	<h3>{$t('referee.matches')}</h3>
	{#each matches as m (m.id)}
		<div class="card match">
			<div class="head">
				<strong>{m.name_a}</strong> <span class="muted">vs</span> <strong>{m.name_b}</strong>
				{#if m.completed}
					<span class="tag"
						>{$t('referee.completedWinner', {
							name: m.winner_id ? winnerName(m) : $t('referee.draw')
						})}</span
					>
				{/if}
			</div>

			<div class="scores">
				<div class="side">
					<div class="muted">{m.name_a}</div>
					<div>Ippon <b>{m.score_a_ippon}</b> · Waza-ari <b>{m.score_a_wazari}</b> · Yuko <b>{m.score_a_yuko}</b></div>
				</div>
				<div class="side">
					<div class="muted">{m.name_b}</div>
					<div>Ippon <b>{m.score_b_ippon}</b> · Waza-ari <b>{m.score_b_wazari}</b> · Yuko <b>{m.score_b_yuko}</b></div>
				</div>
			</div>

			{#if !m.completed}
				<div class="actions">
					<div class="grp">
						<span class="muted">{$t('referee.scoreFor', { name: m.name_a })}</span>
						<button onclick={() => act(() => api.score(m.id, 'a', 'ippon'))} disabled={busy}>Ippon</button>
						<button onclick={() => act(() => api.score(m.id, 'a', 'wazari'))} disabled={busy}>Waza-ari</button>
						<button onclick={() => act(() => api.score(m.id, 'a', 'yuko'))} disabled={busy}>Yuko</button>
					</div>
					<div class="grp">
						<span class="muted">{$t('referee.scoreFor', { name: m.name_b })}</span>
						<button onclick={() => act(() => api.score(m.id, 'b', 'ippon'))} disabled={busy}>Ippon</button>
						<button onclick={() => act(() => api.score(m.id, 'b', 'wazari'))} disabled={busy}>Waza-ari</button>
						<button onclick={() => act(() => api.score(m.id, 'b', 'yuko'))} disabled={busy}>Yuko</button>
					</div>
				</div>
				<div class="end">
					<button class="primary" onclick={() => act(() => api.endMatch(m.id))} disabled={busy}
						>{$t('referee.endMatch')}</button
					>
					<button class="ghost" onclick={() => act(() => api.resetMatch(m.id))} disabled={busy}
						>{$t('referee.resetScores')}</button
					>
				</div>
			{:else}
				<div class="end">
					<button class="ghost" onclick={() => act(() => api.resetMatch(m.id))} disabled={busy}
						>{$t('referee.reopen')}</button
					>
				</div>
			{/if}
		</div>
	{/each}
{/if}

<style>
	.match .head {
		margin-bottom: 0.6rem;
	}
	.scores {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-bottom: 0.6rem;
	}
	.actions {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		border-top: 1px solid var(--border);
		padding-top: 0.7rem;
	}
	.grp {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.grp .muted {
		width: 100%;
		font-size: 0.8rem;
	}
	.end {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.7rem;
		flex-wrap: wrap;
	}

	@media (max-width: 640px) {
		.scores,
		.actions {
			grid-template-columns: 1fr;
		}
	}
</style>
