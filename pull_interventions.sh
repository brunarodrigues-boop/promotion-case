#!/bin/bash
# Pull the intervention figures systems.html needs, from the alpha_dri_interventions source.
#
# Scoped to the source's own published rules, which are not optional:
#   - the two `section` values are INDEPENDENT LOGS; never total across them
#   - a row is a TOUCH, not a failure; the folded case count is reported alongside
#   - `minutes_spent` is Campus DRI time on manual work, `completion_minutes` is
#     Curriculum DRI time answering a request, and the store keeps them disjoint
#   - turnaround is campus_dri only: the subject_dri log is written after the work
#     is done, so elapsed time is undefined there and would come out negative
#
# Writes /tmp/promo/interventions.json and /tmp/promo/deepdive.json.
set -euo pipefail
cd "$(dirname "$0")/../alpha-academic-dashboard"
mkdir -p /tmp/promo

q() { npx -y @insforge/cli db query "$1" 2>&1 | grep -o '{.*}'; }

q "select json_build_object(
 'window', json_build_object('first',min(created_at)::date::text,'last',max(created_at)::date::text,'days',(max(created_at)::date-min(created_at)::date)),
 'campus', json_build_object('touches',count(*) filter (where section='campus_dri'),'cases',(select count(*) from (select distinct email,subject,grade from intervention_requests where section='campus_dri') a),'students',(select count(distinct email) from intervention_requests where section='campus_dri'),'requests',count(*) filter (where section='campus_dri' and entry_kind='intervention_request'),'manual',count(*) filter (where section='campus_dri' and entry_kind='manual_work'),'completed',count(*) filter (where section='campus_dri' and completed),'rejected',count(*) filter (where section='campus_dri' and approval='Rejected'),'open',count(*) filter (where section='campus_dri' and not completed and coalesce(approval,'')<>'Rejected' and not coalesce(archived,false))),
 'curriculum', json_build_object('touches',count(*) filter (where section='subject_dri'),'cases',(select count(*) from (select distinct email,subject,grade from intervention_requests where section='subject_dri') b),'students',(select count(distinct email) from intervention_requests where section='subject_dri'),'completed',count(*) filter (where section='subject_dri' and completed)),
 'turnaround', (select json_build_object('n',count(*),'median_h',round(percentile_cont(0.5) within group (order by h)::numeric,1),'p90_h',round(percentile_cont(0.9) within group (order by h)::numeric,1),'within_8h',round(100.0*count(*) filter (where h<=8)/count(*)),'within_24h',round(100.0*count(*) filter (where h<=24)/count(*)),'within_48h',round(100.0*count(*) filter (where h<=48)/count(*))) from (select extract(epoch from (completed_at-created_at))/3600.0 h from intervention_requests where section='campus_dri' and completed and completed_at>=created_at) t),
 'by_type', (select json_agg(json_build_object('type',rt,'n',n,'median_h',m) order by n desc) from (select coalesce(nullif(request_type,''),'(none)') rt,count(*) n,round(percentile_cont(0.5) within group (order by extract(epoch from (completed_at-created_at))/3600.0)::numeric,1) m from intervention_requests where section='campus_dri' and completed and completed_at>=created_at group by 1 having count(*)>=5) y),
 'type_volume', (select json_agg(json_build_object('type',rt,'n',n) order by n desc) from (select coalesce(nullif(request_type,''),'(none)') rt,count(*) n from intervention_requests where section='campus_dri' group by 1) z),
 'effort', json_build_object('campus_own_min',(select sum(minutes_spent) from intervention_requests where section='campus_dri' and entry_kind='manual_work' and minutes_spent>0),'curriculum_answer_min',(select sum(completion_minutes) from intervention_requests where completion_minutes>0),'campus_own_h',(select round((sum(minutes_spent)/60.0)::numeric,1) from intervention_requests where section='campus_dri' and entry_kind='manual_work' and minutes_spent>0),'campus_own_n',(select count(*) from intervention_requests where section='campus_dri' and entry_kind='manual_work' and minutes_spent>0),'curriculum_answer_h',(select round((sum(completion_minutes)/60.0)::numeric,1) from intervention_requests where completion_minutes>0),'curriculum_answer_n',(select count(*) from intervention_requests where completion_minutes>0),'cm_eligible',(select count(*) from intervention_requests where section='campus_dri' and entry_kind='intervention_request' and completed and created_at>='2026-09-11'),'cm_have',(select count(*) from intervention_requests where section='campus_dri' and entry_kind='intervention_request' and completed and created_at>='2026-09-11' and completion_minutes is not null))
)::text from intervention_requests" > /tmp/promo/interventions.json

q "select json_build_object('requests',count(*),'students',count(distinct email),'open',count(*) filter (where not completed and coalesce(approval,'')<>'Rejected' and not coalesce(archived,false)),'completed',count(*) filter (where completed),'oldest_open_days',max(extract(day from (now()-created_at))) filter (where not completed and coalesce(approval,'')<>'Rejected' and not coalesce(archived,false)))::text from intervention_requests where request_type='Deep dive'" > /tmp/promo/deepdive.json

# The store's own constraints, re-checked. A non-zero count here is a defect
# worth reporting to the source owner, not a number to quietly work around.
q "select json_build_object(
 'completion_minutes_outside_requests',(select count(*) from intervention_requests where completion_minutes is not null and not (section='campus_dri' and entry_kind='intervention_request')),
 'minutes_spent_on_requests',(select count(*) from intervention_requests where minutes_spent is not null and section='campus_dri' and entry_kind='intervention_request'))::text"

python3 -c "
import json
for f in ('interventions','deepdive'):
    print(f, json.load(open(f'/tmp/promo/{f}.json')) if f=='deepdive' else
          json.load(open('/tmp/promo/interventions.json'))['turnaround'])
"
