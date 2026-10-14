<script lang="ts" module>
	export type Option = { id: string; label: string };
</script>

<script lang="ts">
	let {
		options,
		value = $bindable(''),
		placeholder = 'Type a name…',
		exclude = new Set<string>(),
		onselect
	}: {
		options: Option[];
		/** Currently selected option id (two-way bindable). */
		value?: string;
		placeholder?: string;
		/** Option ids to hide from suggestions (e.g. already-chosen members). */
		exclude?: Set<string>;
		onselect: (id: string) => void;
	} = $props();

	const MAX_RESULTS = 8;

	let query = $state('');
	let open = $state(false);
	let highlight = $state(0);

	// Keep the text box in sync when the bound value changes from outside.
	$effect(() => {
		const current = options.find((o) => o.id === value);
		query = current ? current.label : '';
	});

	const matches = $derived.by(() => {
		const q = query.trim().toLowerCase();
		return options
			.filter((o) => !exclude.has(o.id) || o.id === value)
			.filter((o) => !q || o.label.toLowerCase().includes(q))
			.slice(0, MAX_RESULTS);
	});

	function choose(opt: Option) {
		value = opt.id;
		query = opt.label;
		open = false;
		onselect(opt.id);
	}

	function onInput() {
		open = true;
		highlight = 0;
	}

	function onKeydown(e: KeyboardEvent) {
		if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
			open = true;
			return;
		}
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlight = Math.min(highlight + 1, matches.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlight = Math.max(highlight - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (matches[highlight]) choose(matches[highlight]);
		} else if (e.key === 'Escape') {
			open = false;
		}
	}
</script>

<div class="ac">
	<input
		type="text"
		bind:value={query}
		{placeholder}
		oninput={onInput}
		onfocus={() => (open = true)}
		onkeydown={onKeydown}
		onblur={() => (open = false)}
		autocomplete="off"
	/>
	{#if open && matches.length}
		<ul class="menu">
			{#each matches as opt, i (opt.id)}
				<li>
					<button
						type="button"
						class="opt"
						class:active={i === highlight}
						onmouseenter={() => (highlight = i)}
						onmousedown={(e) => e.preventDefault()}
						onclick={() => choose(opt)}
					>
						{opt.label}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.ac {
		position: relative;
	}
	.menu {
		position: absolute;
		z-index: 50;
		top: calc(100% + 2px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 0.25rem;
		list-style: none;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		max-height: 240px;
		overflow-y: auto;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
	}
	.opt {
		display: block;
		width: 100%;
		text-align: left;
		border: none;
		background: transparent;
		padding: 0.4rem 0.55rem;
		border-radius: 6px;
		color: var(--text);
	}
	.opt.active {
		background: var(--accent);
		color: white;
		border-color: var(--accent);
	}
</style>
