"""Guide feedback, and what was done about each piece of it.

Source: the pre-year Campus DRI & coaching survey — 60 responses from 41
campuses, collected 31 July to 6 August 2026. The ten themes below are the
criticism in it, clustered; praise is not listed because a list of compliments
is not evidence of anything.

Status is recorded honestly. "Done" means the thing exists and guides are
receiving it. "In progress" means it is underway and not finished, and two
items say so. One item carries a correction rather than a fix: part of what
guides attributed to DRIs is caused by an automation they cannot see.
"""

SURVEY = {
    "responses": 60,
    "campuses": 41,
    "from": "2026-07-31",
    "to": "2026-08-06",
    "themes": 10,
    # The two questions the criticism came from.
    "q_easier": 60,      # "one thing a Campus DRI could do to make your job easier"
    "q_more_less": 34,   # "anything you wish they had done more of or less of"
}

THEMES = [
 dict(
  n=1, status="done",
  title="Escalations vanished — the loop was never closed",
  quotes=[("Chicago", "It’s been escalated to the appropriate team — with no follow up."),
          ("Austin", "Guides have to escalate 10+ times before anything is done, and there is a "
                     "general feeling that their feedback isn’t really being heard or acted on."),
          ("Spyglass", "Close the loop on feedback.")],
  action="The Slack bot lets a guide query interventions directly and see what is happening "
         "to the thing they raised — without waiting for a DRI to report back. The status is "
         "now something a guide can pull, rather than something they have to chase.",
  kind="Tooling"),

 dict(
  n=2, status="done",
  title="Too many messages, the same information repeated",
  quotes=[("San Francisco", "Less re-alerting to known issues."),
          ("Austin", "Less daily updates of the same information regurgitated."),
          ("Chicago", "Updates too long with important info hidden.")],
  action="This was one campus and one person, not a systemic pattern. That Campus DRI was "
         "moved off the campus, the feedback was handed to their replacement, and the original "
         "DRI was coached on communication practice. They are doing the job well now.",
  kind="People"),

 dict(
  n=3, status="done",
  title="Not proactive — guides were finding the problems first",
  quotes=[("Alpha Southlake", "Be proactive! Don’t wait for me to figure something out and "
                              "reach out."),
          ("Palm Beach", "Identify students that are in doom loops earlier so that we can "
                         "address the issue sooner."),
          ("Denver", "Make us aware when students have taken and failed a mastery test twice.")],
  action="Campus DRIs now work proactively and find issues before a guide raises them. This is "
         "coached continuously rather than announced once — it is a habit, and habits need "
         "maintaining.",
  kind="Practice"),

 dict(
  n=4, status="done",
  title="Blaming the guide instead of fixing the content",
  quotes=[("Chicago", "The feedback frequently sounded like ‘please help motivate them’ when "
                      "significant instructional and content gaps were the real issue."),
          ("Austin", "Less blaming, and more adjusting content to keep data moving."),
          ("Austin Spyglass", "I wish our DRI had been less quick to jump to ‘blaming the guide’.")],
  action="The same person as the message-volume complaint above. Removed from the campus, the "
         "feedback passed to the incoming DRI, and the original DRI coached. Their work has "
         "improved since. Two of the ten themes traced to one individual, which is why the "
         "answer was a personnel decision rather than a process change.",
  kind="People"),

 dict(
  n=5, status="done",
  title="No regular cadence — guides wanted scheduled reports",
  quotes=[("Austin", "Regular weekly reports would have been helpful!"),
          ("Scottsdale", "Send out weekly academic health reports, highlight any flags they’re "
                         "seeing on the academic side and recommendations."),
          ("East Bay / Orlando", "Send weekly updated reports for student progress — where they "
                                 "are currently and where they need to go.")],
  action="Weekly reports now go to every campus, highlighting student performance and the areas "
         "of concern. Not a subset of campuses and not on request: all of them, every week.",
  kind="Tooling"),

 dict(
  n=6, status="done",
  title="Vague advice instead of specific strategies",
  quotes=[("Chantilly", "Less vague suggestions such as ‘they need to work faster’ — we need "
                        "specific strategies from student examples."),
          ("Texas Sports Academy", "More data and specifics; less ‘so how are things?’"),
          ("Brownsville", "Being detailed on what exact skills our students are struggling with.")],
  action="The advice is now specific and names the thing: this student is rushing, this student "
         "is struggling with lesson A or B, this student needs coaching on lesson A. The "
         "difference between that and ‘work faster’ is whether a guide can act on it in the "
         "next session.",
  kind="Practice"),

 dict(
  n=7, status="done",
  title="No advance warning on tests",
  quotes=[("Austin", "Give a one week heads up when a test is approaching, so we can schedule a "
                     "pre-test coaching call prior to the test appearing on the student’s "
                     "dashboard."),
          ("Austin", "Flag newly assigned tests and flag kids who need pretest conversations."),
          ("Scottsdale", "Let us know when there are tests.")],
  action="Guides receive the currently assigned tests every morning, including the attempt "
         "number for that grade and test — so a second or third attempt is visible before the "
         "conversation rather than after it.",
  kind="Tooling"),

 dict(
  n=8, status="partly",
  title="Slow turnaround on deep dives and skill plans",
  quotes=[("Santa Barbara", "Facilitate data and deep dive requests QUICKLY."),
          ("Austin", "Quicker to update students’ skill plans.")],
  action="Two different problems that guides experienced as one. The deep dive delay is real and "
         "is what the Slack bot exists to remove. The skill-plan delay is not a DRI queue at "
         "all — it comes from the automation that generates the plans, so no amount of DRI "
         "responsiveness would have fixed it. Saying so is part of the answer: guides were "
         "chasing the wrong team.",
  kind="Tooling"),

 dict(
  n=9, status="in progress",
  title="No formal route to request things, and every DRI worked differently",
  quotes=[("Austin", "More formalized systems for requesting deep dives, or better understanding "
                     "what DRIs can provide versus what they cannot do at scale."),
          ("NYC", "Have clear, documented decision-making criteria for things like when tests are "
                  "given, how to accelerate levels."),
          ("Austin", "A standardized format across all DRIs would be lovely — lots of variation.")],
  action="Standardising DRI work is underway and not finished. Most DRIs already use the same "
         "format for deep dives and reports, which is the majority of the variation guides were "
         "seeing, but it is convention rather than standard until it is written down and "
         "enforced.",
  kind="Practice"),

 dict(
  n=10, status="partly",
  title="Availability, and the timezone gap on the West Coast",
  quotes=[("Santa Barbara", "I just wish they were in a closer time zone for the West Coast. The "
                            "communication was sometimes inconsistent due to time constraints."),
          ("Spyglass", "Be available during the school hours when I have an urgent question.")],
  action="Every Campus DRI is now required to be available during core hours. The timezone half "
         "is not solved by a rule — a hiring request is in, asking that core hours be allowed to "
         "run to 2pm CT depending on the DRI’s timezone, so West Coast campuses get covered by "
         "someone whose day overlaps theirs.",
  kind="People"),
]
