<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { get } from 'svelte/store';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import Autocomplete, { type Option } from '$lib/components/Autocomplete.svelte';
	import { t, locale } from '$lib/i18n';
	import ScoringPanel from '$lib/components/ScoringPanel.svelte';
	import type { Club, Group, Member, Participant, RefereeToken, Tournament } from '$lib/types';

	const participantCols = $derived<Column[]>([
		{ key: 'member_name', label: $t('common.name') },
		{ key: 'gender', label: $t('common.gender') },
		{
			key: 'weight',
			label: $t('common.weight'),
			numeric: true,
			format: (p) => (p.weight != null ? `${p.weight} kg` : '—'),
			sortValue: (p) => p.weight ?? -1
		},
		{ key: 'age_category', label: $t('common.category'), format: (p) => p.age_category || '—' },
		{ key: 'group_name', label: $t('common.group'), format: (p) => p.group_name ?? '—' }
	]);

	const tid = $derived($page.params.id ?? '');

	let clubs = $state<Club[]>([]);
	let tournament = $state<Tournament | null>(null);
	let error = $state('');
	let busy = $state(false);
	let notFound = $state(false);

	// detail state
	let participants = $state<Participant[]>([]);
	let groups = $state<Group[]>([]);
	let tokens = $state<RefereeToken[]>([]);
	let tab = $state<'participants' | 'groups' | 'scores' | 'tokens'>('participants');

	// register form
	let regClub = $state('');
	let clubMembers = $state<Member[]>([]);
	let selectedMembers = $state<Record<string, boolean>>({});
	// group config
	let maxSize = $state(4);
	let extra = $state(2);
	// token create form (per role) + inline edit state
	let newLabel = $state<Record<string, string>>({ referee: '', inscription: '' });
	let newToken = $state<Record<string, string>>({ referee: '', inscription: '' });
	let editId = $state<string | null>(null);
	let editValue = $state('');
	let editLabel = $state('');

	const refereeTokens = $derived(tokens.filter((tk) => tk.role !== 'inscription'));
	const inscriptionTokens = $derived(tokens.filter((tk) => tk.role === 'inscription'));

	// print / export filters
	let pdfGender = $state('all');
	let pdfClub = $state('all');
	let pdfGroup = $state('all');
	let downloading = $state(false);

	async function downloadPdf() {
		downloading = true;
		error = '';
		try {
			const params = new URLSearchParams();
			if (pdfGender !== 'all') params.set('gender', pdfGender);
			if (pdfClub !== 'all') params.set('club_id', pdfClub);
			if (pdfGroup !== 'all') params.set('group_id', pdfGroup);
			params.set('lang', get(locale));
			const qs = params.toString() ? `?${params}` : '';
			const blob = await api.participantsPdf(tid, qs);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `participants-${tournament?.name ?? tid}.pdf`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			error = msg(e);
		} finally {
			downloading = false;
		}
	}

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	onMount(async () => {
		try {
			clubs = await api.listClubs();
			if (clubs.length) regClub = clubs[0].id;
		} catch (e) {
			error = msg(e);
		}
	});

	// Load the tournament + its detail whenever the id in the URL changes.
	$effect(() => {
		if (tid) loadTournament(tid);
	});

	async function loadTournament(id: string) {
		error = '';
		notFound = false;
		try {
			tournament = await api.getTournament(id);
			await loadDetail(id);
		} catch (e) {
			tournament = null;
			if (e instanceof ApiError && e.status === 404) notFound = true;
			else error = msg(e);
		}
	}
	$effect(() => {
		if (regClub) loadClubMembers(regClub);
	});

	async function loadDetail(id: string) {
		error = '';
		try {
			[participants, groups, tokens] = await Promise.all([
				api.listParticipants(id),
				api.listGroups(id),
				api.listTokens(id)
			]);
		} catch (e) {
			error = msg(e);
		}
	}

	async function loadClubMembers(clubId: string) {
		try {
			clubMembers = await api.listMembers(clubId);
		} catch {
			clubMembers = [];
		}
	}

	const registeredMemberIds = $derived(new Set(participants.map((p) => p.member_id)));
	const availableMembers = $derived(clubMembers.filter((m) => !registeredMemberIds.has(m.id)));

	async function registerSelected() {
		const ids = Object.entries(selectedMembers)
			.filter(([, v]) => v)
			.map(([k]) => k);
		if (!ids.length) return;
		busy = true;
		try {
			await api.registerParticipants(tid, ids);
			selectedMembers = {};
			await loadDetail(tid);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function generate() {
		busy = true;
		error = '';
		try {
			groups = await api.generateGroups(tid, maxSize, extra);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	// --- Group editing --------------------------------------------------
	let editingGroupId = $state<string | null>(null);
	let editIds = $state<string[]>([]);
	let addValue = $state('');

	const participantOptions = $derived<Option[]>(
		participants.map((p) => ({
			id: p.id,
			label: `${p.member_name} (${p.weight ?? '?'}kg, ${p.gender})`
		}))
	);

	// Participants not assigned to any pool yet (shown as a heads-up at the top).
	const unassignedParticipants = $derived(participants.filter((p) => p.group_id === null));

	// Members in the pool currently being edited that belong to another pool —
	// saving will move them out of it. Drives the in-panel warning.
	const movedMembers = $derived.by(() => {
		if (!editingGroupId) return [];
		return editIds
			.map((id) => participants.find((p) => p.id === id))
			.filter((p): p is Participant => !!p && !!p.group_id && p.group_id !== editingGroupId)
			.map((p) => ({ name: p.member_name, from: p.group_name ?? 'another pool' }));
	});

	function startEdit(g: Group) {
		editingGroupId = g.id;
		editIds = g.participants.map((p) => p.id);
		addValue = '';
	}

	function cancelEdit() {
		editingGroupId = null;
		editIds = [];
		addValue = '';
	}

	function replaceAt(i: number, id: string) {
		// Ignore if the picked participant is already elsewhere in this pool.
		if (editIds.includes(id) && editIds[i] !== id) return;
		editIds = editIds.map((x, j) => (j === i ? id : x));
	}

	function removeAt(i: number) {
		editIds = editIds.filter((_, j) => j !== i);
	}

	function addMember(id: string) {
		if (!editIds.includes(id)) editIds = [...editIds, id];
		addValue = '';
	}

	async function saveEdit() {
		if (!editingGroupId) return;
		busy = true;
		error = '';
		try {
			groups = await api.setGroupParticipants(tid, editingGroupId, editIds);
			participants = await api.listParticipants(tid);
			cancelEdit();
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function setStatus(status: 'open' | 'closed') {
		if (!tournament || tournament.status === status) return;
		busy = true;
		error = '';
		try {
			tournament = await api.setTournamentStatus(tid, status);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function saveReweigh(months: number) {
		if (!tournament || !Number.isFinite(months) || months < 1 || months === tournament.reweigh_months)
			return;
		busy = true;
		error = '';
		try {
			tournament = await api.setTournamentSettings(tid, months);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	async function addToken(role: 'referee' | 'inscription') {
		const label = (newLabel[role] ?? '').trim();
		if (!label) return;
		busy = true;
		error = '';
		try {
			await api.createToken(tid, { label, role, token: (newToken[role] ?? '').trim() || undefined });
			newLabel = { ...newLabel, [role]: '' };
			newToken = { ...newToken, [role]: '' };
			tokens = await api.listTokens(tid);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}

	function startEditToken(tk: RefereeToken) {
		editId = tk.id;
		editValue = tk.token;
		editLabel = tk.label;
	}

	async function saveToken() {
		if (!editId) return;
		busy = true;
		error = '';
		try {
			await api.updateToken(tid, editId, { token: editValue.trim(), label: editLabel.trim() });
			editId = null;
			tokens = await api.listTokens(tid);
		} catch (e) {
			error = msg(e);
		} finally {
			busy = false;
		}
	}
</script>

<a class="back" href="/admin/tournaments">← {$t('detail.back')}</a>

{#if error}<p class="error">{error}</p>{/if}

{#if notFound}
	<p class="muted">{$t('detail.notFound')} <a href="/admin/tournaments">{$t('detail.backToList')}</a></p>
{:else if tournament}
	<div class="title-row">
		<div>
			<h1>{tournament.name}</h1>
			<p class="muted subtitle">
				{tournament.date}{tournament.location ? ` · ${tournament.location}` : ''}
			</p>
		</div>
		<div class="settings">
			<div class="status">
				<span class="muted">{$t('detail.status')}</span>
				<div class="mode-switch" role="group" aria-label={$t('detail.status')}>
					<button class:active={tournament.status === 'closed'} onclick={() => setStatus('closed')}
						>{$t('detail.statusClosed')}</button
					>
					<button class:active={tournament.status === 'open'} onclick={() => setStatus('open')}
						>{$t('detail.statusOpen')}</button
					>
				</div>
			</div>
			<div class="reweigh-setting">
				<label for="rw">{$t('detail.reweighMonths')}</label>
				<input
					id="rw"
					type="number"
					min="1"
					max="36"
					value={tournament.reweigh_months}
					disabled={busy}
					onchange={(e) => saveReweigh(Number((e.target as HTMLInputElement).value))}
				/>
			</div>
		</div>
	</div>

	<div class="tabs">
		<button class="ghost" class:active={tab === 'participants'} onclick={() => (tab = 'participants')}
			>{$t('detail.tabParticipants')}</button
		>
		<button class="ghost" class:active={tab === 'groups'} onclick={() => (tab = 'groups')}
			>{$t('detail.tabGroups')}</button
		>
		<button class="ghost" class:active={tab === 'scores'} onclick={() => (tab = 'scores')}
			>{$t('detail.tabScores')}</button
		>
		<button class="ghost" class:active={tab === 'tokens'} onclick={() => (tab = 'tokens')}
			>{$t('detail.tabTokens')}</button
		>
	</div>

	{#if tab === 'participants'}
		<div class="card">
			<h3>{$t('detail.registeredCount', { count: participants.length })}</h3>
			{#if participants.length}
				<DataTable columns={participantCols} rows={participants} />
			{/if}
		</div>

		<div class="card">
			<h3>{$t('detail.registerParticipants')}</h3>
			<div class="field" style="max-width:320px">
				<label for="rc">{$t('detail.fromClub')}</label>
				<select id="rc" bind:value={regClub}>
					{#each clubs as c}<option value={c.id}>{c.name}</option>{/each}
				</select>
			</div>
			{#if availableMembers.length === 0}
				<p class="muted">{$t('detail.allRegistered')}</p>
			{:else}
				<div class="checklist">
					{#each availableMembers as m}
						<label class="check">
							<input type="checkbox" bind:checked={selectedMembers[m.id]} />
							{m.first_name} {m.last_name} ({m.weight ?? '?'}kg, {m.gender})
						</label>
					{/each}
				</div>
				<button class="primary" style="margin-top:.6rem" onclick={registerSelected} disabled={busy}
					>{$t('detail.registerSelected')}</button
				>
			{/if}
		</div>

		<div class="card">
			<h3>{$t('print.title')}</h3>
			<p class="muted">{$t('print.intro')}</p>
			<div class="row" style="max-width:640px">
				<div>
					<label for="pg">{$t('common.gender')}</label>
					<select id="pg" bind:value={pdfGender}>
						<option value="all">{$t('print.allGenders')}</option>
						<option value="M">M</option>
						<option value="F">F</option>
					</select>
				</div>
				<div>
					<label for="pc">{$t('common.club')}</label>
					<select id="pc" bind:value={pdfClub}>
						<option value="all">{$t('print.allClubs')}</option>
						{#each clubs as c}<option value={c.id}>{c.name}</option>{/each}
					</select>
				</div>
				<div>
					<label for="pp">{$t('common.group')}</label>
					<select id="pp" bind:value={pdfGroup}>
						<option value="all">{$t('print.allPools')}</option>
						{#each groups as g}<option value={g.id}>{g.name}</option>{/each}
						<option value="unassigned">{$t('print.unassigned')}</option>
					</select>
				</div>
			</div>
			<button class="primary" style="margin-top:.6rem" onclick={downloadPdf} disabled={downloading}>
				🖨 {downloading ? $t('print.preparing') : $t('print.download')}
			</button>
		</div>
	{:else if tab === 'groups'}
		<div class="card">
			{#if groups.length}
				{#if unassignedParticipants.length}
					<div class="warn-snippet">
						⚠ {$t('detail.unassignedWarn', { count: unassignedParticipants.length })}
						{unassignedParticipants.map((p) => p.member_name).join(', ')}.
						<span class="muted">{$t('detail.editToAdd')}</span>
					</div>
				{/if}
				<p class="muted edit-note">{$t('detail.editNote')}</p>
				{#each groups as g (g.id)}
					<div class="pool">
						<div class="pool-head">
							<div>
								<strong>{g.name}</strong>
								<span class="tag"
									>{editingGroupId === g.id ? editIds.length : g.participants.length}
									{$t('detail.participantsSuffix')}</span
								>
							</div>
							{#if editingGroupId === g.id}
								<div class="pool-actions">
									<button class="primary" onclick={saveEdit} disabled={busy}>{$t('common.save')}</button>
									<button class="ghost" onclick={cancelEdit} disabled={busy}>{$t('common.cancel')}</button>
								</div>
							{:else}
								<button
									class="ghost"
									onclick={() => startEdit(g)}
									disabled={busy || editingGroupId !== null}>{$t('common.edit')}</button
								>
							{/if}
						</div>

						{#if editingGroupId === g.id}
							{#if movedMembers.length}
								<div class="warn-snippet move">
									⚠ {$t('detail.movedWarn')}
									{#each movedMembers as mm, i}
										<strong>{mm.name}</strong>
										<span class="muted">({$t('detail.fromPool', { pool: mm.from })})</span>{i <
										movedMembers.length - 1
											? ', '
											: ''}
									{/each}
								</div>
							{/if}
							<div class="edit-rows">
								{#each editIds as pid, i (pid + ':' + i)}
									<div class="edit-row">
										<Autocomplete
											options={participantOptions}
											value={pid}
											exclude={new Set(editIds.filter((_, j) => j !== i))}
											onselect={(id) => replaceAt(i, id)}
										/>
										<button
											class="danger ghost remove"
											title={$t('detail.removeFromPool')}
											onclick={() => removeAt(i)}>✕</button
										>
									</div>
								{/each}
								<div class="edit-row">
									<Autocomplete
										options={participantOptions}
										bind:value={addValue}
										placeholder={$t('detail.addMember')}
										exclude={new Set(editIds)}
										onselect={addMember}
									/>
								</div>
							</div>
						{:else}
							<ul>
								{#each g.participants as p}
									<li>{p.member_name} ({p.weight ?? '?'}kg, {p.gender})</li>
								{/each}
							</ul>
						{/if}
					</div>
				{/each}
			{:else if participants.length >= 2}
				<h3>{$t('detail.generateGroupsTitle')}</h3>
				<div class="row" style="max-width:520px">
					<div>
						<label for="ms">{$t('detail.maxGroupSize', { n: maxSize })}</label>
						<input id="ms" type="range" min="3" max="6" bind:value={maxSize} />
					</div>
					<div>
						<label for="ex">{$t('detail.maxAdditionalGroups', { n: extra })}</label>
						<input id="ex" type="range" min="0" max="4" bind:value={extra} />
					</div>
				</div>
				<button class="primary" style="margin-top:.6rem" onclick={generate} disabled={busy}>
					{busy ? $t('detail.runningSolver') : $t('detail.generateRun')}
				</button>
			{:else}
				<p class="muted">{$t('detail.needTwo')}</p>
			{/if}
		</div>
	{:else if tab === 'scores'}
		<ScoringPanel tournamentId={tid} />
	{:else}
		{#each [{ role: 'referee', title: $t('detail.refereeTokens'), list: refereeTokens }, { role: 'inscription', title: $t('detail.inscriptionTokens'), list: inscriptionTokens }] as section (section.role)}
			<div class="card">
				<h3>{section.title}</h3>
				{#if section.list.length === 0}
					<p class="muted">{$t('detail.noTokens')}</p>
				{/if}
				{#each section.list as tk (tk.id)}
					<div class="token-row">
						{#if editId === tk.id}
							<input class="tk-label" bind:value={editLabel} placeholder={$t('detail.tokenLabel')} />
							<input class="tk-value" bind:value={editValue} placeholder={$t('detail.tokenValue')} />
							<button class="primary" onclick={saveToken} disabled={busy}>{$t('detail.saveToken')}</button>
							<button class="ghost" onclick={() => (editId = null)} disabled={busy}>{$t('common.cancel')}</button>
						{:else}
							<span class="tag">{tk.label}</span>
							<code>{tk.token}</code>
							<button class="ghost" onclick={() => startEditToken(tk)}>{$t('common.edit')}</button>
						{/if}
					</div>
				{/each}
				<div class="row" style="max-width:520px; margin-top:.7rem">
					<input placeholder={$t('detail.tokenLabel')} bind:value={newLabel[section.role]} />
					<input placeholder={$t('detail.customTokenOptional')} bind:value={newToken[section.role]} />
					<button
						class="primary"
						onclick={() => addToken(section.role as 'referee' | 'inscription')}
						disabled={busy || !newLabel[section.role]}>{$t('detail.addToken')}</button
					>
				</div>
			</div>
		{/each}
	{/if}
{:else}
	<p class="muted">{$t('common.loading')}</p>
{/if}

<style>
	.back {
		display: inline-block;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}
	.subtitle {
		margin-top: -0.4rem;
	}
	.title-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.settings {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-end;
	}
	.status {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.reweigh-setting {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.reweigh-setting label {
		margin: 0;
	}
	.reweigh-setting input {
		width: 4.5rem;
	}
	.mode-switch {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.mode-switch button {
		border: none;
		border-radius: 0;
		background: var(--surface);
		padding: 0.4rem 0.9rem;
		color: var(--muted);
	}
	.mode-switch button + button {
		border-left: 1px solid var(--border);
	}
	.mode-switch button.active {
		background: var(--accent);
		color: white;
	}
	.token-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 0.3rem 0;
	}
	.token-row .tk-label {
		max-width: 180px;
	}
	.token-row .tk-value {
		max-width: 220px;
	}
	.tabs {
		display: flex;
		gap: 0.4rem;
		margin: 1rem 0;
		flex-wrap: wrap;
	}
	.tabs button.active {
		background: var(--surface-2);
		border-color: var(--accent);
		color: var(--text);
	}
	.checklist {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 0.3rem;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		color: var(--text);
		margin: 0;
		font-size: 0.92rem;
	}
	.check input {
		width: auto;
	}
	.pool {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.6rem 0.8rem;
		margin-bottom: 0.6rem;
	}
	.pool ul {
		margin: 0.4rem 0 0;
		padding-left: 1.1rem;
	}
	.pool-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.pool-actions {
		display: flex;
		gap: 0.4rem;
	}
	.edit-note {
		font-size: 0.85rem;
		margin-top: 0;
	}
	.warn-snippet {
		background: rgba(229, 150, 0, 0.12);
		border: 1px solid rgba(229, 150, 0, 0.5);
		color: #f0c674;
		border-radius: var(--radius);
		padding: 0.55rem 0.75rem;
		font-size: 0.88rem;
		margin-bottom: 0.75rem;
		line-height: 1.5;
	}
	.warn-snippet.move {
		margin: 0.6rem 0;
	}
	.warn-snippet :global(.muted) {
		color: #c9a86a;
	}
	.edit-rows {
		margin-top: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}
	.edit-row {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.edit-row :global(.ac) {
		flex: 1;
	}
	.edit-row .remove {
		padding: 0.5rem 0.7rem;
		line-height: 1;
	}
	input[type='range'] {
		width: 100%;
	}
</style>
