# Owner navigation and Hunter feedback repair

- Ava example now has a Back to my idea control; original opportunity and saved form values are retained. Create an agent also exits the example. Removed the intermediate example recommendation auto-scroll.
- Refresh inbox now reports checking, completion time/count or failure, and explains that refreshing saved records is not live web research.
- Removed the old prepare-refresh/copy-request route from the owner inbox UI. Its backend record format remains untouched for compatibility.
- The primary action is Research & prepare this agent, calling the existing automatic fresh-company research → Aria → OMNARA → Troy preparation lane. The selected card shows actual server stage messages, elapsed time and a working indicator, then the real final state and an explicit Open prepared package action. No automatic scroll is required to notice status.
- Stale Hunter sales qualification is NOT automatically renewed. This change connects agent preparation without manual bot handoffs, not autonomous GTM requalification or outreach.
- Browser regression covers leaving the example without losing the original idea; save/reopen/build remains intact. Delayed fixture responses verify inbox feedback, preparation feedback, and absence of copy-request controls. No provider calls were made for this UI repair. Existing server serves the new static assets; refresh the browser to load them.
