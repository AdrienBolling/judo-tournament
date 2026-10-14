<script lang="ts">
	import '../app.css';
	import { auth, logout } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { t, locale, setLocale, LOCALES } from '$lib/i18n';
	import type { Role } from '$lib/types';

	let { children } = $props();

	type NavItem = { href: string; key: string };

	const NAV: Record<Role, NavItem[]> = {
		admin: [
			{ href: '/admin/tournaments', key: 'nav.tournaments' },
			{ href: '/admin/clubs', key: 'nav.clubs' },
			{ href: '/coach/members', key: 'nav.members' },
			{ href: '/coach/results', key: 'nav.results' }
		],
		coach: [
			{ href: '/coach/members', key: 'nav.members' },
			{ href: '/coach/results', key: 'nav.results' }
		],
		referee: [{ href: '/referee', key: 'nav.scoring' }],
		inscription: [{ href: '/inscriptions', key: 'nav.inscriptions' }]
	};

	const navItems = $derived($auth ? NAV[$auth.role] : []);
	const onLoginPage = $derived($page.url.pathname === '/login');

	let menuOpen = $state(false);

	// Guard: bounce unauthenticated users to /login (except the login page itself).
	$effect(() => {
		if (!$auth && !onLoginPage) goto('/login');
	});

	// Close the mobile menu whenever the route changes.
	$effect(() => {
		$page.url.pathname;
		menuOpen = false;
	});

	function doLogout() {
		logout();
		goto('/login');
	}
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key === 'Escape') menuOpen = false;
	}}
/>

{#if $auth && !onLoginPage}
	<nav class="topnav" class:open={menuOpen}>
		<div class="brand">🥋 Judo Manager</div>

		<button
			class="burger"
			class:open={menuOpen}
			aria-label={$t('nav.menuToggle')}
			aria-expanded={menuOpen}
			aria-controls="nav-body"
			onclick={() => (menuOpen = !menuOpen)}
		>
			<span></span><span></span><span></span>
		</button>

		<div id="nav-body" class="nav-body" class:open={menuOpen}>
			<div class="links">
				{#each navItems as item}
					<a href={item.href} class:active={$page.url.pathname.startsWith(item.href)}
						>{$t(item.key)}</a
					>
				{/each}
			</div>
			<div class="user">
				<div class="lang" role="group" aria-label="Language">
					{#each LOCALES as l}
						<button
							class="lang-btn"
							class:active={$locale === l.code}
							onclick={() => setLocale(l.code)}>{l.label}</button
						>
					{/each}
				</div>
				<span class="muted">{$auth.display_name}</span>
				<button class="ghost" onclick={doLogout}>{$t('common.logout')}</button>
			</div>
		</div>
	</nav>

	<!-- Click-away backdrop for the open mobile menu. -->
	{#if menuOpen}
		<button class="backdrop" aria-label={$t('nav.closeMenu')} onclick={() => (menuOpen = false)}
		></button>
	{/if}
{/if}

<main class="container">
	{@render children()}
</main>

<style>
	.topnav {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 0.7rem 1.5rem;
		background: var(--surface);
		border-bottom: 1px solid var(--border);
		position: sticky;
		top: 0;
		z-index: 30;
	}
	.brand {
		font-weight: 700;
		white-space: nowrap;
	}
	.nav-body {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 1.5rem;
	}
	.links {
		display: flex;
		gap: 0.4rem;
		flex: 1;
		flex-wrap: wrap;
	}
	.links a {
		color: var(--muted);
		padding: 0.35rem 0.7rem;
		border-radius: var(--radius);
		white-space: nowrap;
	}
	.links a:hover {
		color: var(--text);
		background: var(--surface-2);
	}
	.links a.active {
		color: var(--text);
		background: var(--surface-2);
	}
	.user {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		white-space: nowrap;
	}
	.lang {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.lang-btn {
		border: none;
		border-radius: 0;
		background: var(--surface);
		color: var(--muted);
		padding: 0.25rem 0.55rem;
		font-size: 0.78rem;
	}
	.lang-btn + .lang-btn {
		border-left: 1px solid var(--border);
	}
	.lang-btn.active {
		background: var(--accent);
		color: white;
	}

	/* Hamburger button — hidden on desktop. */
	.burger {
		display: none;
		flex-direction: column;
		justify-content: center;
		gap: 5px;
		width: 42px;
		height: 38px;
		padding: 0;
		margin-left: auto;
	}
	.burger span {
		display: block;
		width: 20px;
		height: 2px;
		margin: 0 auto;
		background: var(--text);
		transition: transform 0.2s ease, opacity 0.2s ease;
	}
	.burger.open span:nth-child(1) {
		transform: translateY(7px) rotate(45deg);
	}
	.burger.open span:nth-child(2) {
		opacity: 0;
	}
	.burger.open span:nth-child(3) {
		transform: translateY(-7px) rotate(-45deg);
	}

	.backdrop {
		display: none;
	}

	/* ---- Mobile: collapse nav into the burger dropdown ---- */
	@media (max-width: 768px) {
		.topnav {
			gap: 1rem;
			padding: 0.6rem 1rem;
		}
		.burger {
			display: flex;
		}
		.nav-body {
			position: absolute;
			top: 100%;
			left: 0;
			right: 0;
			flex-direction: column;
			align-items: stretch;
			gap: 0.4rem;
			padding: 0.75rem 1rem 1rem;
			background: var(--surface);
			border-bottom: 1px solid var(--border);
			box-shadow: 0 14px 28px rgba(0, 0, 0, 0.4);
			/* Hidden until the burger toggles it. */
			display: none;
		}
		.nav-body.open {
			display: flex;
		}
		.links {
			flex-direction: column;
			gap: 0.15rem;
		}
		.links a {
			padding: 0.6rem 0.7rem;
		}
		.user {
			justify-content: space-between;
			border-top: 1px solid var(--border);
			margin-top: 0.3rem;
			padding-top: 0.7rem;
		}
		.backdrop {
			display: block;
			position: fixed;
			inset: 0;
			top: 0;
			z-index: 20;
			border: none;
			border-radius: 0;
			background: rgba(0, 0, 0, 0.35);
		}
	}
</style>
