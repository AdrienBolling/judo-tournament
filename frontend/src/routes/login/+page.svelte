<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { setAuth } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n';
	import { get } from 'svelte/store';
	import type { PublicTournament, TokenResponse } from '$lib/types';

	type Tab = 'coach' | 'admin' | 'referee' | 'inscription';
	let tab = $state<Tab>('coach');
	let error = $state('');
	let busy = $state(false);
	let needsSetup = $state(false);
	let checking = $state(true);

	// coach fields
	let email = $state('');
	let coachPwd = $state('');
	// admin fields
	let username = $state('');
	let adminPwd = $state('');
	// token-based fields (referee + inscription)
	let token = $state('');
	let openTournaments = $state<PublicTournament[]>([]);
	let selectedOpen = $state<PublicTournament | null>(null);
	// setup fields
	let setupUser = $state('');
	let setupPwd = $state('');
	let setupConfirm = $state('');

	const isTokenTab = $derived(tab === 'referee' || tab === 'inscription');

	onMount(async () => {
		try {
			needsSetup = (await api.setupStatus()).needs_setup;
		} catch {
			/* backend down — show login anyway */
		} finally {
			checking = false;
		}
		try {
			openTournaments = await api.openTournaments();
		} catch {
			/* no public list available — token entry still works */
		}
	});

	function pickTab(next: Tab) {
		tab = next;
		error = '';
		selectedOpen = null;
		token = '';
	}

	function selectOpen(tn: PublicTournament) {
		selectedOpen = tn;
		token = '';
		error = '';
	}

	function submitToken() {
		const tid = selectedOpen?.id;
		run(() =>
			tab === 'inscription' ? api.loginInscription(token, tid) : api.loginReferee(token, tid)
		);
	}

	async function run(fn: () => Promise<TokenResponse>) {
		error = '';
		busy = true;
		try {
			const t = await fn();
			setAuth(t);
			goto('/');
		} catch (e) {
			error = e instanceof ApiError ? e.message : get(t)('common.somethingWrong');
		} finally {
			busy = false;
		}
	}

	function doSetup() {
		if (!setupUser || !setupPwd) {
			error = get(t)('login.usernamePasswordRequired');
			return;
		}
		if (setupPwd !== setupConfirm) {
			error = get(t)('login.passwordsNoMatch');
			return;
		}
		run(() => api.setupAdmin(setupUser, setupPwd));
	}
</script>

<div class="wrap">
	<h1>🥋 {$t('login.title')}</h1>

	{#if checking}
		<p class="muted">{$t('common.loading')}</p>
	{:else if needsSetup}
		<div class="card">
			<h2>{$t('login.setupTitle')}</h2>
			<p class="muted">{$t('login.setupIntro')}</p>
			<div class="field">
				<label for="su">{$t('login.adminUsername')}</label>
				<input id="su" bind:value={setupUser} />
			</div>
			<div class="field">
				<label for="sp">{$t('common.password')}</label>
				<input id="sp" type="password" bind:value={setupPwd} />
			</div>
			<div class="field">
				<label for="sc">{$t('login.confirmPassword')}</label>
				<input id="sc" type="password" bind:value={setupConfirm} />
			</div>
			{#if error}<p class="error">{error}</p>{/if}
			<button class="primary" onclick={doSetup} disabled={busy}>{$t('login.createAdmin')}</button>
		</div>
	{:else}
		<div class="card">
			<div class="tabs">
				<button class:active={tab === 'coach'} class="ghost" onclick={() => pickTab('coach')}
					>{$t('login.tabCoach')}</button
				>
				<button class:active={tab === 'admin'} class="ghost" onclick={() => pickTab('admin')}
					>{$t('login.tabAdmin')}</button
				>
				<button class:active={tab === 'referee'} class="ghost" onclick={() => pickTab('referee')}
					>{$t('login.tabReferee')}</button
				>
				<button
					class:active={tab === 'inscription'}
					class="ghost"
					onclick={() => pickTab('inscription')}>{$t('login.tabInscription')}</button
				>
			</div>

			{#if tab === 'coach'}
				<div class="field">
					<label for="ce">{$t('common.email')}</label>
					<input id="ce" bind:value={email} />
				</div>
				<div class="field">
					<label for="cp">{$t('common.password')}</label>
					<input
						id="cp"
						type="password"
						bind:value={coachPwd}
						onkeydown={(e) => e.key === 'Enter' && run(() => api.loginCoach(email, coachPwd))}
					/>
				</div>
				<button class="primary" disabled={busy} onclick={() => run(() => api.loginCoach(email, coachPwd))}
					>{$t('login.loginBtn')}</button
				>
			{:else if tab === 'admin'}
				<div class="field">
					<label for="au">{$t('login.username')}</label>
					<input id="au" bind:value={username} />
				</div>
				<div class="field">
					<label for="ap">{$t('common.password')}</label>
					<input
						id="ap"
						type="password"
						bind:value={adminPwd}
						onkeydown={(e) => e.key === 'Enter' && run(() => api.loginAdmin(username, adminPwd))}
					/>
				</div>
				<button
					class="primary"
					disabled={busy}
					onclick={() => run(() => api.loginAdmin(username, adminPwd))}>{$t('login.loginBtn')}</button
				>
			{:else if isTokenTab}
				{#if !selectedOpen}
					<p class="muted">{$t('login.selectOpenTournament')}</p>
					{#if openTournaments.length === 0}
						<p class="muted">{$t('login.noOpenTournaments')}</p>
					{:else}
						<div class="open-list">
							{#each openTournaments as tn (tn.id)}
								<button class="open-item" onclick={() => selectOpen(tn)}>
									<span class="open-name">{tn.name}</span>
									<span class="muted">{tn.date}{tn.location ? ` · ${tn.location}` : ''}</span>
								</button>
							{/each}
						</div>
					{/if}
				{:else}
					<button class="link" onclick={() => (selectedOpen = null)}
						>{$t('login.changeTournament')}</button
					>
					<p class="selected-name">{selectedOpen.name}</p>
					<div class="field">
						<label for="rt"
							>{tab === 'inscription'
								? $t('login.inscriptionToken')
								: $t('login.tournamentToken')}</label
						>
						<input id="rt" bind:value={token} onkeydown={(e) => e.key === 'Enter' && submitToken()} />
					</div>
					<button class="primary" disabled={busy} onclick={submitToken}>{$t('login.enterBtn')}</button>
				{/if}
			{/if}

			{#if error}<p class="error">{error}</p>{/if}
		</div>
	{/if}
</div>

<style>
	.wrap {
		max-width: 420px;
		margin: 4rem auto;
	}
	.tabs {
		display: flex;
		gap: 0.4rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.tabs button.active {
		background: var(--surface-2);
		border-color: var(--accent);
		color: var(--text);
	}
	.open-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.5rem;
	}
	.open-item {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.15rem;
		text-align: left;
		padding: 0.6rem 0.75rem;
	}
	.open-item:hover {
		border-color: var(--accent);
	}
	.open-name {
		font-weight: 600;
	}
	.selected-name {
		font-weight: 650;
		margin: 0.3rem 0 0.6rem;
	}
</style>
