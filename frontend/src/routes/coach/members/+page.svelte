<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import { t } from '$lib/i18n';
	import type { Club, Member } from '$lib/types';

	const memberCols = $derived<Column[]>([
		{ key: 'last_name', label: $t('common.lastName') },
		{ key: 'first_name', label: $t('common.firstName') },
		{ key: 'gender', label: $t('common.gender') },
		{
			key: 'weight',
			label: $t('common.weight'),
			numeric: true,
			format: (m) => (m.weight != null ? `${m.weight} kg` : '—'),
			sortValue: (m) => m.weight ?? -1
		},
		{ key: 'date_of_birth', label: $t('members.dob'), format: (m) => m.date_of_birth ?? '—' },
		{ key: 'age_category', label: $t('common.category'), format: (m) => m.age_category || '—' }
	]);

	let clubs = $state<Club[]>([]);
	let clubId = $state('');
	let members = $state<Member[]>([]);
	let error = $state('');
	let notice = $state('');
	let busy = $state(false);
	const isAdmin = $derived($auth?.role === 'admin');

	// add / edit form (weight & DOB optional; filled in later if blank)
	let editingId = $state<string | null>(null);
	let fn = $state('');
	let ln = $state('');
	let dob = $state('');
	let gender = $state('M');
	// number input binds as number | null (null when empty).
	let weightVal = $state<number | null>(null);
	// csv
	let csvFile = $state<FileList | null>(null);

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));
	const incompleteMembers = $derived(members.filter((m) => !m.is_complete));

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
		if (clubId) loadMembers(clubId);
	});

	async function loadMembers(id: string) {
		error = '';
		try {
			members = await api.listMembers(id);
		} catch (e) {
			error = msg(e);
		}
	}

	function resetForm() {
		editingId = null;
		fn = ln = dob = '';
		weightVal = null;
		gender = 'M';
	}

	function startEdit(m: Member) {
		editingId = m.id;
		fn = m.first_name;
		ln = m.last_name;
		gender = m.gender;
		dob = m.date_of_birth ?? '';
		weightVal = m.weight;
		if (typeof window !== 'undefined') window.scrollTo({ top: document.body.scrollHeight });
	}

	async function save() {
		if (!fn || !ln) {
			error = get(t)('members.firstLastRequired');
			return;
		}
		busy = true;
		error = notice = '';
		try {
			const weight = weightVal == null ? undefined : weightVal;
			const date_of_birth = dob || undefined;
			if (editingId) {
				await api.updateMember(editingId, { first_name: fn, last_name: ln, gender, date_of_birth, weight });
			} else {
				await api.createMember(clubId, {
					first_name: fn,
					last_name: ln,
					gender,
					date_of_birth: date_of_birth ?? null,
					weight: weight ?? null
				});
			}
			resetForm();
			await loadMembers(clubId);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function importCsv() {
		if (!csvFile || csvFile.length === 0) return;
		busy = true;
		error = notice = '';
		try {
			const imported = await api.importMembers(clubId, csvFile[0]);
			notice = get(t)('members.imported', { count: imported.length });
			csvFile = null;
			await loadMembers(clubId);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}
</script>

<h1>{$t('members.title')}</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if notice}<p class="ok">{notice}</p>{/if}

{#if isAdmin}
	<div class="field" style="max-width:360px">
		<label for="club">{$t('members.selectClub')}</label>
		<select id="club" bind:value={clubId}>
			{#each clubs as c}<option value={c.id}>{c.name}</option>{/each}
		</select>
	</div>
{/if}

{#if incompleteMembers.length}
	<div class="warn-snippet">
		⚠ {$t('members.incompleteWarn', { n: incompleteMembers.length })}
		{incompleteMembers.map((m) => `${m.first_name} ${m.last_name}`).join(', ')}.
	</div>
{/if}

<div class="card">
	<h2>{$t('clubs.members')} <span class="tag">{members.length}</span></h2>
	<DataTable columns={memberCols} rows={members} empty={$t('members.noMembers')}>
		{#snippet actions(m)}
			<button class="ghost" onclick={() => startEdit(m)}>{$t('common.edit')}</button>
		{/snippet}
	</DataTable>
</div>

<div class="card">
	<h2>{editingId ? $t('members.editing', { name: `${fn} ${ln}` }) : $t('members.addMember')}</h2>
	<div class="row">
		<input placeholder={$t('common.firstName')} bind:value={fn} />
		<input placeholder={$t('common.lastName')} bind:value={ln} />
		<div>
			<label for="g">{$t('common.gender')}</label>
			<select id="g" bind:value={gender}><option>M</option><option>F</option></select>
		</div>
	</div>
	<div class="row" style="margin-top:.5rem">
		<div>
			<label for="dob">{$t('members.dob')} <span class="muted">({$t('members.optional')})</span></label>
			<input id="dob" type="date" bind:value={dob} />
		</div>
		<div>
			<label for="w">{$t('members.weightKg')} <span class="muted">({$t('members.optional')})</span></label>
			<input id="w" type="number" min="10" max="200" step="0.5" bind:value={weightVal} />
		</div>
	</div>
	<div class="form-actions">
		<button class="primary" onclick={save} disabled={busy}>
			{editingId ? $t('common.save') : $t('members.addMember')}
		</button>
		{#if editingId}
			<button class="ghost" onclick={resetForm} disabled={busy}>{$t('common.cancel')}</button>
		{/if}
	</div>
</div>

<div class="card">
	<h2>{$t('members.importTitle')}</h2>
	<p class="muted">
		{$t('members.importColsPre')}
		<code>first_name, last_name, date_of_birth, weight, gender</code>
	</p>
	<input type="file" accept=".csv" onchange={(e) => (csvFile = (e.target as HTMLInputElement).files)} />
	<button class="primary" style="margin-top:.6rem" onclick={importCsv} disabled={busy || !csvFile?.length}
		>{$t('members.import')}</button
	>
</div>

<style>
	.warn-snippet {
		background: rgba(229, 150, 0, 0.12);
		border: 1px solid rgba(229, 150, 0, 0.5);
		color: #f0c674;
		border-radius: var(--radius);
		padding: 0.55rem 0.75rem;
		font-size: 0.9rem;
		margin-bottom: 1rem;
		line-height: 1.5;
	}
	.form-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.6rem;
	}
</style>
