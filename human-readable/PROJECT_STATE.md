# PROJECT STATE — read this first (written for an undergrad RA)

AGENT-MAINTAINED: the director rewrites this file at every round close, in
this register — plain language, no jargon without a one-line explanation,
no result numbers typed by hand (point to files instead).

## What this project is, in one paragraph

When countries get into conflicts, they sometimes close their airspace to
each other's airlines — like when Russia banned European airlines from
flying over Siberia in 2022, so a London–Tokyo flight suddenly had to take
a huge detour and got about two hours longer. Our idea: you can *measure*
international tensions by watching flight times. If British planes to Asia
suddenly take longer but Chinese planes on the same route don't, something
political happened between specific countries. That gives us a "tension
index" between pairs of countries that updates constantly and doesn't
depend on reading news articles (which are mostly in English and biased
toward what journalists notice).

## How we measure it (toddler version)

1. For each route (like Chicago→Tokyo) and each airline's home country, we
   compute the normal flight time (the typical value over the past three
   years, same month of the year — because winds differ by season).
2. "Excess time" = this month's actual flight time minus that normal.
3. If excess time stays high for a while (not just one stormy week), and it
   only happens to SOME countries' airlines on that route, we flag a
   bilateral disruption. If it happens to everyone equally, it's probably
   weather patterns, a volcano, or a war zone closed to all — still
   logged, but different.

## Where the data comes from

- A free US government dataset (called T-100) with monthly flight times
  for every airline flying into or out of the US, back to 1990.
- A plane-tracking network (OpenSky) with detailed daily data for
  2019–2022, which we use to double-check that our flight-time trick
  actually detects the real detours we can see in the tracking data.

## Major narratives tested so far / what happened

- (nothing yet — project just set up; first round will build the data)

## Dead ends and failures (so you don't redo them)

- (none yet)

## What's happening next

- Round 1: download and clean T-100, build the route × airline-country ×
  month panel, and make the first raw plots around February 2022.
