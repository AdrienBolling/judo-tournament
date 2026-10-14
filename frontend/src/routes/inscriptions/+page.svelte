<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { auth } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { t } from '$lib/i18n';
	import type { RegistrationRow, Tournament } from '$lib/types';

	// Inscription staff are scoped to the tournament their token granted.
	const tournamentId = $derived($auth?.tournament_id ?? '');
	let tournament = $state<Tournament | null>(null);
	let rows = $state<RegistrationRow[]>([]);
	let query = $state('');
	let error = $state('');
	let busyIds = $state<Record<string, boolean>>({});

	const msg = (e: unknown) => (e instanceof ApiError ? e.message : get(t)('common.somethingWrong'));

	onMount(async () => {
		if (!tournamentId) return;
		try {
			[tournament, rows] = await Promise.all([
				api.getTournament(tournamentId),
				api.registrationList(tournamentId)
			]);
		} catch (e) {
			error = msg(e);
		}
	});

	const filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		if (!q) return rows;
		return rows.filter(
			(r) => r.member_name.toLowerCase().includes(q) || r.club_name.toLowerCase().includes(q)
		);
	});

	const registeredCount = $derived(rows.filter((r) => r.registered).length);

	async function toggle(row: RegistrationRow) {
		busyIds = { ...busyIds, [row.member_id]: true };
		error = '';
		const next = !row.registered;
		try {
			if (next) await api.registerParticipants(tournamentId, [row.member_id]);
			else await api.unregisterParticipant(tournamentId, row.member_id);
			// Reflect the change locally.
			rows = rows.map((r) => (r.member_id === row.member_id ? { ...r, registered: next } : r));
		} catch (e) {
			error = msg(e);
		} finally {
			busyIds = { ...busyIds, [row.member_id]: false };
		}
	}

	// --- Inline member editing (incl. weigh-in) ---------------------------
	let editId = $state<string | null>(null);
	let eFirst = $state('');
	let eLast = $state('');
	let eGender = $state('M');
	let eWeight = $state<number | null>(null);
	let saving = $state(false);

	function startEdit(row: RegistrationRow) {
		editId = row.member_id;
		eFirst = row.first_name;
		eLast = row.last_name;
		eGender = row.gender;
		eWeight = row.weight;
	}

	async function saveEdit() {
		if (!editId) return;
		saving = true;
		error = '';
		try {
			await api.updateMember(editId, {
				first_name: eFirst,
				last_name: eLast,
				gender: eGender,
				weight: eWeight == null ? undefined : eWeight
			});
			editId = null;
			// Refetch so staleness + displayed values recompute.
			rows = await api.registrationList(tournamentId);
		} catch (e) {
			error = msg(e);
		} finally {
			saving = false;
		}
	}
</script>

<h1>{$t('inscription.title')}</h1>
{#if tournament}<h2>{tournament.name}</h2>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if !tournamentId}
	<p class="muted">{$t('inscription.noTournament')}</p>
{:else}
	<div class="bar">
		<input class="search" placeholder={$t('inscription.search')} bind:value={query} />
		<span class="tag">{$t('inscription.registeredCount', { n: registeredCount })}</span>
	</div>

	{#if filtered.length === 0}
		<p class="muted">{$t('inscription.empty')}</p>
	{:else}
		<div class="list">
			{#each filtered as row (row.member_id)}
				<div class="reg-row" class:on={row.registered} class:stale={row.weight_stale}>
					{#if editId === row.member_id}
						<div class="edit-grid">
							<input bind:value={eFirst} placeholder={$t('common.firstName')} />
							<input bind:value={eLast} placeholder={$t('common.lastName')} />
							<select bind:value={eGender}><option>M</option><option>F</option></select>
							<input type="number" min="10" max="200" step="0.1" bind:value={eWeight} />
							<button class="primary" onclick={saveEdit} disabled={saving}>{$t('common.save')}</button>
							<button class="ghost" onclick={() => (editId = null)} disabled={saving}
								>{$t('common.cancel')}</button
							>
						</div>
					{:else}
						<label class="main">
							<input
								type="checkbox"
								checked={row.registered}
								disabled={busyIds[row.member_id]}
								onchange={() => toggle(row)}
							/>
							<span class="who">
								<span class="name">{row.member_name}</span>
								<span class="muted"
								>{row.club_name} · {row.gender} · {row.weight != null
									? `${row.weight} kg`
									: '—'}</span
							>
							</span>
						</label>
						<span class="meta">
							{#if row.weight_stale}
								<span class="reweigh" title={row.weight_updated_at
									? $t('inscription.weighedOn', { date: row.weight_updated_at })
									: $t('inscription.neverWeighed')}>⚠ {$t('inscription.reweighWarn')}</span
								>
							{:else if row.weight_updated_at}
								<span class="muted small">{$t('inscription.weighedOn', { date: row.weight_updated_at })}</span>
							{/if}
							<button class="ghost edit-btn" onclick={() => startEdit(row)}>{$t('common.edit')}</button>
						</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{/if}

<style>
	.bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.9rem;
		flex-wrap: wrap;
	}
	.search {
		flex: 1;
		min-width: 200px;
		max-width: 420px;
	}
	.list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.reg-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.7rem;
		margin: 0;
		padding: 0.55rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		flex-wrap: wrap;
	}
	.reg-row.on {
		border-color: var(--accent);
		background: var(--surface-2);
	}
	.reg-row.stale {
		border-color: rgba(229, 150, 0, 0.6);
	}
	.main {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		margin: 0;
		cursor: pointer;
		flex: 1;
		min-width: 200px;
	}
	.main input {
		width: auto;
	}
	.who {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.name {
		font-weight: 600;
	}
	.meta {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.reweigh {
		color: #f0c674;
		font-size: 0.85rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.small {
		font-size: 0.8rem;
	}
	.edit-grid {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		align-items: center;
		width: 100%;
	}
	.edit-grid input,
	.edit-grid select {
		width: auto;
		flex: 1;
		min-width: 90px;
	}
</style>
