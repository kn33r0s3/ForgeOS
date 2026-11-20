# Hami live audio room — semantics contract

Status: AUTHORISED by Niroj, 20 Nov 2026 ~20:38 +0545 ("ok continue" — a green light to proceed, not a confirmation of the definitions; corrected 23:01 from ACCEPTED). Acceptance (test T1) is pending his confirmation of three open points: reconnect-window duration, the enumerated counter set, exact first-rung figures. Merged into ForgeOS `docs/`. The audio harness is built to this page. Nothing in this page decides hosting, pricing, or payout rails — those stay undecided.

## Why this page exists

Everything measured so far is 5 fps video-frame fanout. The audio product is a different thing: Opus audio, speakers, listeners, hand-raises, stage seats. This page pins the words before any architecture is drawn, so "50 speakers / 10,000 listeners in one room" means one thing everywhere.

## The terms

**Room.** One logical live session. A room is an ENTITY (`entity_type="room"`) with an owner, a stage, and an audience. Room states: scheduled, live, ended. One room is one room — a listener in room A never receives audio from room B.

**Speaker.** A participant holding a stage seat. A speaker publishes exactly one audio stream. Target maximum: 50 speakers in one room. A speaker who stops publishing keeps the seat until they leave or are removed — silence is not leaving.

**Listener.** A participant subscribed to a room's audio who does not publish. Target maximum: 10,000 listeners in one room. Listeners receive audio; they never send it.

**Stage.** The set of current speakers in a room (at most 50). Joining the stage, leaving it, being moved to it, and being removed from it are all EVENTs with a reason and an actor recorded.

**Subscription.** The RELATION between a participant and a room, with a role (speaker or listener) and a state (joined, left). A subscription is created on join and closed on leave. A reconnect is not a new subscription: a listener who drops and rejoins within the reconnect window (duration unpinned — open point for T1 confirmation) resumes the same subscription, and the drop and the resume are counted separately from a fresh join.

**Hand-raise.** A listener's request for a stage seat. It is an EVENT, not a seat. Granting it moves the listener to the stage (a second EVENT); declining it closes the request (also an EVENT). Nothing is a stage seat until the grant EVENT exists.

**Audio packet.** One Opus frame from one speaker. Audio latency is capture-to-render for audio, measured on an audio frame clock — the video FrameClock is not an audio metric and must never be quoted as one.

**Loss, jitter, reconnects.** Counted separately per listener, per speaker stream. A lost packet, a late packet, and a reconnect are three different counters, never merged into one "quality" number.

## Distribution — two candidate modes, decision deferred to measurement

**Mixing:** the server mixes all speakers into one stream per listener. **Selective forwarding:** each speaker's stream is forwarded and the listener's device mixes. The harness must measure both on the same rungs before either is chosen. No mode is the default until a measurement says so. OPEN QUESTION (23:01, answered before the mode is chosen): do listeners ever need different speaker subsets? If every listener hears the same mix, one mix serves all 10,000 and mixing wins on egress and compute; if subsets differ, selective forwarding stays in play.

## What maps onto the existing system (no new tables)

Room = ENTITY. Speaker/listener role = RELATION. Join, leave, hand-raise, grant, decline, mute, kick, ban = EVENT. A mute, kick, or ban carries a reason and becomes a Judgment with Evidence attached; an appeal is a second Judgment linked to the first. No audio is stored — evidence is the EVENT plus its metadata, never a recording.

## What this page does NOT decide

- Hosting. The Mac is the development and experimentation environment, not the production server. Production hosting is undecided.
- Opus bitrate, frame size, or mix parameters. Those come from the harness measurements, not from this page.
- Creator economics or payout rails. Those use the existing payment tables and are a separate slice.
- The video ladder. The video capacity work continues on its own rungs; it is not the audio proof and its numbers are never quoted as audio numbers.

## Acceptance (test T1)

This page was authorised when Niroj replied "ok continue" (20 Nov 2026 ~20:38 +0545). It is NOT yet accepted: acceptance (test T1) requires his confirmation in his own words of (1) the reconnect-window duration, (2) the enumerated counter set (loss, jitter, reconnects — and T3 must count jitter separately), (3) the exact first-rung figures. It is merged into `docs/` and the audio harness (first rung: 10 speakers × 10 listeners — corrected 23:01 from ~10×100) is built to exactly these definitions.
