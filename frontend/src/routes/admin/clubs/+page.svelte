<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import { t } from '$lib/i18n';
	import type { Club, Coach, Member } from '$lib/types';

	const coachCols = $derived<Column[]>([
		{
			key: 'name',
			label: $t('common.name'),
			format: (c) => `${c.first_name} ${c.last_name}`,
			sortValue: (c) => `${c.last_name} ${c.first_name}`
		},
		{ key: 'email', label: $t('common.email') },
		{ key: 'phone_number', label: $t('common.phone') }
	]);

	const memberCols = $derived<Column[]>([
		{
			key: 'name',
			label: $t('common.name'),
			format: (m) => `${m.first_name} ${m.last_name}`,
			sortValue: (m) => `${m.last_name} ${m.first_name}`
		},
		{ key: 'gender', label: $t('common.gender') },
		{
			key: 'weight',
			label: $t('common.weight'),
			numeric: true,
			format: (m) => (m.weight != null ? `${m.weight} kg` : '—'),
			sortValue: (m) => m.weight ?? -1
		},
		{ key: 'age_category', label: $t('common.category'), format: (m) => m.age_category || '—' }
	]);

	let clubs = $state<Club[]>([]);
	let selectedId = $state('');
	let coaches = $state<Coach[]>([]);
	let members = $state<Member[]>([]);
	let error = $state('');
	let busy = $state(false);

	// new club
	let clubName = $state('');
	let clubLoc = $state('');
	// new coach
	let cFn = $state('');
	let cLn = $state('');
	let cEmail = $state('');
	let cPhone = $state('');
	let cPwd = $state('');

	const selected = $derived(clubs.find((c) => c.id === selectedId) ?? null);

	onMount(loadClubs);

	async function loadClubs() {
		try {
			clubs = await api.listClubs();
			if (clubs.length && !selectedId) selectedId = clubs[0].id;
		} catch (e) {
			error = msg(e);
		}
	}

	$effect(() => {
		if (selectedId) loadClubDetail(selectedId);
	});

	async function loadClubDetail(id: string) {
		error = '';
		try {
			[coaches, members] = await Promise.all([api.listCoaches(id), api.listMembers(id)]);
		} catch (e) {
			error = msg(e);
		}
	}

	async function createClub() {
		if (!clubName) return;
		busy = true;
		try {
			const c = await api.createClub(clubName, clubLoc);
			clubName = clubLoc = '';
			await loadClubs();
			selectedId = c.id;
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function addCoach() {
		if (!cFn || !cLn || !cEmail || !cPwd) {
			error = get(t)('clubs.coachRequired');
			return;
		}
		busy = true;
		try {
			await api.createCoach(selectedId, {
				first_name: cFn,
				last_name: cLn,
				email: cEmail,
				phone_number: cPhone,
				password: cPwd
			});
			cFn = cLn = cEmail = cPhone = cPwd = '';
			await loadClubDetail(selectedId);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function removeCoach(id: string) {
		busy = true;
		try {
			await api.deleteCoach(id);
			await loadClubDetail(selectedId);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));
</script>

<h1>{$t('clubs.title')}</h1>
{#if error}<p class="error">{error}</p>{/if}

<div class="card">
	<h2>{$t('clubs.createClub')}</h2>
	<div class="row">
		<input placeholder={$t('clubs.clubName')} bind:value={clubName} />
		<input placeholder={$t('common.location')} bind:value={clubLoc} />
		<button class="primary" onclick={createClub} disabled={busy || !clubName}>{$t('common.create')}</button>
	</div>
</div>

{#if clubs.length === 0}
	<p class="muted">{$t('clubs.noClubs')}</p>
{:else}
	<div class="field" style="max-width:360px">
		<label for="club">{$t('clubs.selectClub')}</label>
		<select id="club" bind:value={selectedId}>
			{#each clubs as c}
				<option value={c.id}>{c.name} ({c.location})</option>
			{/each}
		</select>
	</div>

	<div class="card">
		<h2>{$t('clubs.coaches')}</h2>
		<DataTable columns={coachCols} rows={coaches} empty={$t('clubs.noCoaches')}>
			{#snippet actions(coach)}
				<button class="danger" onclick={() => removeCoach(coach.id)} disabled={busy}
					>{$t('common.remove')}</button
				>
			{/snippet}
		</DataTable>

		<h3 style="margin-top:1.2rem">{$t('clubs.addCoach')}</h3>
		<div class="row">
			<input placeholder={$t('common.firstName')} bind:value={cFn} />
			<input placeholder={$t('common.lastName')} bind:value={cLn} />
		</div>
		<div class="row" style="margin-top:.5rem">
			<input placeholder={$t('common.email')} bind:value={cEmail} />
			<input placeholder={$t('common.phone')} bind:value={cPhone} />
			<input placeholder={$t('common.password')} type="password" bind:value={cPwd} />
		</div>
		<button class="primary" style="margin-top:.6rem" onclick={addCoach} disabled={busy}
			>{$t('clubs.addCoach')}</button
		>
	</div>

	<div class="card">
		<h2>{$t('clubs.members')} <span class="tag">{members.length}</span></h2>
		<DataTable columns={memberCols} rows={members} empty={$t('clubs.noMembers')} />
	</div>
{/if}
