<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { get } from 'svelte/store';
	import { t } from '$lib/i18n';
	import type { Club, Tournament } from '$lib/types';

	let clubs = $state<Club[]>([]);
	let tournaments = $state<Tournament[]>([]);
	let error = $state('');
	let busy = $state(false);

	// Pick what you're doing first: create a new tournament, or manage one.
	let mode = $state<'create' | 'manage'>('manage');

	// create-tournament form
	let tName = $state('');
	let tDate = $state(new Date().toISOString().slice(0, 10));
	let tLoc = $state('');
	let tClub = $state('');

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	onMount(async () => {
		try {
			[clubs, tournaments] = await Promise.all([api.listClubs(), api.listTournaments()]);
			if (clubs.length) tClub = clubs[0].id;
			mode = tournaments.length ? 'manage' : 'create';
		} catch (e) {
			error = msg(e);
		}
	});

	async function createTournament() {
		if (!tName || !tClub) return;
		busy = true;
		error = '';
		try {
			const t = await api.createTournament({
				name: tName,
				date: tDate,
				location: tLoc,
				hosting_club_id: tClub
			});
			// Straight to the new tournament's dedicated page.
			goto(`/admin/tournaments/${t.id}`);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}
</script>

<h1>{$t('tournaments.title')}</h1>
{#if error}<p class="error">{error}</p>{/if}

<div class="mode-switch" role="group" aria-label="Tournament mode">
	<button class:active={mode === 'create'} onclick={() => (mode = 'create')}>＋ {$t('tournaments.create')}</button>
	<button class:active={mode === 'manage'} onclick={() => (mode = 'manage')}>⚙ {$t('tournaments.manage')}</button>
</div>

{#if mode === 'create'}
	<div class="card">
		<h2>{$t('tournaments.createNew')}</h2>
		{#if clubs.length === 0}
			<p class="muted">{$t('tournaments.createClubFirst')}</p>
		{:else}
			<div class="row">
				<input placeholder={$t('common.name')} bind:value={tName} />
				<input type="date" bind:value={tDate} />
			</div>
			<div class="row" style="margin-top:.5rem">
				<input placeholder={$t('common.location')} bind:value={tLoc} />
				<select bind:value={tClub}>
					{#each clubs as c}<option value={c.id}>{c.name}</option>{/each}
				</select>
				<button class="primary" onclick={createTournament} disabled={busy || !tName}
					>{$t('common.create')}</button
				>
			</div>
		{/if}
	</div>
{:else if tournaments.length === 0}
	<p class="muted">
		{$t('tournaments.switchToCreatePre')}
		<button class="link" onclick={() => (mode = 'create')}>{$t('tournaments.create')}</button>
		{$t('tournaments.switchToCreatePost')}
	</p>
{:else}
	<p class="muted">{$t('tournaments.chooseToManage')}</p>
	<div class="t-grid">
		{#each tournaments as tour (tour.id)}
			<a class="t-card" href={`/admin/tournaments/${tour.id}`}>
				<div class="t-name">{tour.name}</div>
				<div class="muted t-meta">{tour.date}{tour.location ? ` · ${tour.location}` : ''}</div>
				<div class="t-go">{$t('tournaments.manageArrow')}</div>
			</a>
		{/each}
	</div>
{/if}

<style>
	.mode-switch {
		display: inline-flex;
		margin-bottom: 1.25rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.mode-switch button {
		border: none;
		border-radius: 0;
		background: var(--surface);
		padding: 0.55rem 1.2rem;
		color: var(--muted);
	}
	.mode-switch button + button {
		border-left: 1px solid var(--border);
	}
	.mode-switch button.active {
		background: var(--accent);
		color: white;
	}
	.t-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 0.85rem;
	}
	.t-card {
		display: block;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 1rem 1.1rem;
		color: var(--text);
		transition: border-color 0.12s ease, transform 0.12s ease;
	}
	.t-card:hover {
		border-color: var(--accent);
		transform: translateY(-2px);
	}
	.t-name {
		font-weight: 650;
		font-size: 1.05rem;
		margin-bottom: 0.2rem;
	}
	.t-meta {
		font-size: 0.85rem;
	}
	.t-go {
		margin-top: 0.7rem;
		color: var(--accent);
		font-size: 0.85rem;
	}
</style>
