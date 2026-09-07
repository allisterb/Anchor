// Policy fixture for the differential test.
//
// Real Cedar, evaluated by the real engine. The translator turns this same file into the
// TLA+ policy data, so both sides are driven by one artifact rather than two hand-written ones.
//
// Deliberately chosen to exercise the decision ordering rather than to be realistic: overlapping
// permits, a forbid that shadows one of them, and a rate limit that only bites above a threshold.

// Anyone may search.
permit (
    principal,
    action == Action::"search",
    resource
);

// Users may read files, but only for the first three calls of a session.
permit (
    principal,
    action == Action::"read_file",
    resource
)
when { context.session.call_count < 3 };

// Admins may do anything, including delete.
permit (
    principal == Admin::"root",
    action,
    resource
);

// Nobody deletes files. This forbid must beat the admin permit above -- if the model gets
// forbid-overrides-permit wrong, this is the request where it shows.
forbid (
    principal,
    action == Action::"delete_file",
    resource
);
