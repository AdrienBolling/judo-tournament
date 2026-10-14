<script lang="ts" module>
	export type Column<Row = any> = {
		/** Unique key; also used as the default sort accessor (`row[key]`). */
		key: string;
		label: string;
		/** Right-align + numeric-aware sorting. */
		numeric?: boolean;
		/** Set false to make the column non-sortable. */
		sortable?: boolean;
		/** Display formatter; defaults to `row[key]`. */
		format?: (row: Row) => string;
		/** Sort accessor override (useful for composite/formatted columns). */
		sortValue?: (row: Row) => string | number;
	};
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		columns,
		rows,
		actions,
		actionsLabel = '',
		empty = 'No data.'
	}: {
		columns: Column[];
		rows: any[];
		/** Optional trailing cell per row (e.g. a delete button). */
		actions?: Snippet<[any]>;
		actionsLabel?: string;
		empty?: string;
	} = $props();

	let sortKey = $state<string | null>(null);
	let sortDir = $state<'asc' | 'desc'>('asc');

	function toggle(col: Column) {
		if (col.sortable === false) return;
		if (sortKey === col.key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = col.key;
			sortDir = 'asc';
		}
	}

	function sortVal(col: Column, row: any): string | number {
		if (col.sortValue) return col.sortValue(row);
		const v = row[col.key];
		return v ?? '';
	}

	const sorted = $derived.by(() => {
		if (!sortKey) return rows;
		const col = columns.find((c) => c.key === sortKey);
		if (!col) return rows;
		const dir = sortDir === 'asc' ? 1 : -1;
		// Array.sort is stable in modern engines, so equal rows keep their order.
		return [...rows].sort((a, b) => {
			const va = sortVal(col, a);
			const vb = sortVal(col, b);
			if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
			return String(va).localeCompare(String(vb), undefined, { numeric: true }) * dir;
		});
	});
</script>

<div class="table-wrap">
	<table>
		<thead>
			<tr>
				{#each columns as col (col.key)}
					<th
						class:numeric={col.numeric}
						class:sortable={col.sortable !== false}
						aria-sort={sortKey === col.key
							? sortDir === 'asc'
								? 'ascending'
								: 'descending'
							: 'none'}
						onclick={() => toggle(col)}
					>
						<span class="th-inner">
							{col.label}
							{#if col.sortable !== false}
								<span class="arrow" class:active={sortKey === col.key}>
									{sortKey === col.key ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
								</span>
							{/if}
						</span>
					</th>
				{/each}
				{#if actions}<th>{actionsLabel}</th>{/if}
			</tr>
		</thead>
		<tbody>
			{#if sorted.length === 0}
				<tr>
					<td class="muted" colspan={columns.length + (actions ? 1 : 0)}>{empty}</td>
				</tr>
			{:else}
				{#each sorted as row (row.id ?? JSON.stringify(row))}
					<tr>
						{#each columns as col (col.key)}
							<td class:numeric={col.numeric}>
								{col.format ? col.format(row) : (row[col.key] ?? '—')}
							</td>
						{/each}
						{#if actions}<td class="actions-cell">{@render actions(row)}</td>{/if}
					</tr>
				{/each}
			{/if}
		</tbody>
	</table>
</div>

<style>
	.table-wrap {
		width: 100%;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
	}
	th.sortable {
		cursor: pointer;
		user-select: none;
		white-space: nowrap;
	}
	th.sortable:hover {
		color: var(--text);
	}
	.th-inner {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.arrow {
		font-size: 0.7rem;
		opacity: 0.35;
	}
	.arrow.active {
		opacity: 1;
		color: var(--accent);
	}
	td.numeric,
	th.numeric {
		text-align: right;
	}
	.actions-cell {
		text-align: right;
		white-space: nowrap;
	}
</style>
