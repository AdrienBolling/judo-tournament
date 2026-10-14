<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { t } from '$lib/i18n';

	// Landing route: send each role to its home page.
	$effect(() => {
		const a = $auth;
		if (!a) {
			goto('/login');
		} else if (a.role === 'admin') {
			goto('/admin/tournaments');
		} else if (a.role === 'coach') {
			goto('/coach/members');
		} else if (a.role === 'inscription') {
			goto('/inscriptions');
		} else {
			goto('/referee');
		}
	});
</script>

<p class="muted">{$t('common.redirecting')}</p>
