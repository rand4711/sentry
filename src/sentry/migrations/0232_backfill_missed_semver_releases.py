# Generated by Django 2.2.24 on 2021-09-23 14:02
# Copied from 0223_semver_backfill_2.py
from django.db import connection, migrations
from psycopg2.extras import execute_values
from sentry_relay.exceptions import RelayError
from sentry_relay.processing import parse_release

from sentry.utils.query import RangeQuerySetWrapperWithProgressBar

BATCH_SIZE = 100


def convert_build_code_to_build_number(build_code):
    # Taken from `ReleaseModelManager._convert_build_code_to_build_number`
    build_number = None
    if build_code is not None:
        try:
            build_code_as_int = int(build_code)
            if validate_bigint(build_code_as_int):
                build_number = build_code_as_int
        except ValueError:
            pass
    return build_number


def validate_bigint(value):
    return isinstance(value, int) and value >= 0 and value.bit_length() <= 63


UPDATE_QUERY = """
    UPDATE sentry_release
    SET package = data.package,
    major = data.major::bigint,
    minor = data.minor::bigint,
    patch = data.patch::bigint,
    revision = data.revision::bigint,
    prerelease = data.prerelease,
    build_code = data.build_code,
    build_number = data.build_number::bigint
    FROM (VALUES %s) AS data (id, package, major, minor, patch, revision, prerelease, build_code, build_number)
    WHERE sentry_release.id = data.id"""

SEMVER_FIELDS = ["package", "major", "minor", "patch", "revision", "prerelease", "build_code"]


def backfill_semver(apps, schema_editor):
    Release = apps.get_model("sentry", "Release")
    queryset = RangeQuerySetWrapperWithProgressBar(
        Release.objects.values_list(
            "pk",
            "version",
            "package",
            "major",
            "minor",
            "patch",
            "revision",
            "prerelease",
            "build_code",
            "build_number",
        ),
        result_value_getter=lambda item: item[0],
    )
    cursor = connection.cursor()
    batch = []
    for pk, version, *semver_fields in queryset:
        try:
            version_info = parse_release(version)
        except RelayError:
            continue

        version_parsed = version_info.get("version_parsed")
        if version_parsed is None:
            # If the parsed version isn't valid semver, but the stored release has a package, that
            # means it incorrectly translated as semver previously, so we want to set the semver
            # fields to None
            if semver_fields[0] is None:
                continue

            batch.append((pk, None, None, None, None, None, None, None, None))
        else:
            bigint_fields = ["major", "minor", "patch", "revision"]
            if not all(validate_bigint(version_parsed[field]) for field in bigint_fields):
                continue

            build_code = version_parsed.get("build_code")
            build_number = convert_build_code_to_build_number(build_code)

            new_vals = [
                version_info["package"],
                version_parsed["major"],
                version_parsed["minor"],
                version_parsed["patch"],
                version_parsed["revision"],
                version_parsed["pre"] or "",
                build_code,
                build_number,
            ]

            if semver_fields != new_vals:
                batch.append((pk, *new_vals))

        if len(batch) >= BATCH_SIZE:
            execute_values(cursor, UPDATE_QUERY, batch, page_size=BATCH_SIZE)
            batch = []

    if batch:
        execute_values(cursor, UPDATE_QUERY, batch, page_size=BATCH_SIZE)


class Migration(migrations.Migration):
    # This flag is used to mark that a migration shouldn't be automatically run in
    # production. We set this to True for operations that we think are risky and want
    # someone from ops to run manually and monitor.
    # General advice is that if in doubt, mark your migration as `is_dangerous`.
    # Some things you should always mark as dangerous:
    # - Large data migrations. Typically we want these to be run manually by ops so that
    #   they can be monitored. Since data migrations will now hold a transaction open
    #   this is even more important.
    # - Adding columns to highly active tables, even ones that are NULL.
    is_dangerous = True

    # This flag is used to decide whether to run this migration in a transaction or not.
    # By default we prefer to run in a transaction, but for migrations where you want
    # to `CREATE INDEX CONCURRENTLY` this needs to be set to False. Typically you'll
    # want to create an index concurrently when adding one to an existing table.
    # You'll also usually want to set this to `False` if you're writing a data
    # migration, since we don't want the entire migration to run in one long-running
    # transaction.
    atomic = False

    dependencies = [
        ("sentry", "0231_alert_rule_comparison_delta"),
    ]

    operations = [
        migrations.RunPython(
            backfill_semver,
            migrations.RunPython.noop,
            hints={"tables": ["sentry_release"]},
        ),
    ]
