
# Integration pattern for the EXISTING Writify Studio app.
from writify_live_workflow import runtime, render_workflow, started, completed, failed, skipped

rt=runtime()
render_workflow(user_query,rt,"Research","Running")

# Around each EXISTING real CrewAI task:
# started(rt,"researcher",user_query)
# render_workflow(user_query,rt,"Research","Running")
# result=EXISTING_RESEARCH_CALL(...)
# completed(rt,"researcher","Research Package",{"Sources": actual_source_count})
#
# Repeat for blog_writer, linkedin_writer, twitter_writer, seo_editor, fact_checker.
# For an unselected output: skipped(rt,"twitter_writer","Not selected")
# For a real exception: failed(rt,"linkedin_writer","Could not generate output.")
#
# Final:
# render_workflow(user_query,rt,"Final Package","Completed")
