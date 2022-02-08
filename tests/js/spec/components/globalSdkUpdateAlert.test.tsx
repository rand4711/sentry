import moment from 'moment';

import {mountWithTheme, screen, userEvent} from 'sentry-test/reactTestingLibrary';

import {InnerGlobalSdkUpdateAlert} from 'sentry/components/globalSdkUpdateAlert';
import {ALL_ACCESS_PROJECTS} from 'sentry/constants/pageFilters';
import {PageFilters, ProjectSdkUpdates} from 'sentry/types';
import {DEFAULT_SNOOZE_PROMPT_DAYS} from 'sentry/utils/promptIsDismissed';
import {OrganizationContext} from 'sentry/views/organizationContext';

const makeFilterProps = (filters: Partial<PageFilters>): PageFilters => {
  return {
    projects: [1],
    environments: ['prod'],
    datetime: {start: new Date(), end: new Date(), period: '14d', utc: true},
    ...filters,
  };
};

const makeSdkUpdateProps = (
  sdkUpdateProps: Partial<ProjectSdkUpdates>
): ProjectSdkUpdates[] => {
  return [
    {
      projectId: String(1),
      sdkName: 'sentry-javascript',
      sdkVersion: '1.0.0.',
      suggestions: [
        {
          enables: [],
          newSdkVersion: '1.1.0',
          sdkName: 'sentry-javascript',
          type: 'updateSdk',
        },
      ],
      ...sdkUpdateProps,
    },
  ];
};

describe('GlobalSDKUpdateAlert', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockApiClient.clearMockResponses();
  });

  it('does not shows prompt if projects do not match', async () => {
    // We have matching projectId, so updates should be show
    const filters: PageFilters = makeFilterProps({projects: [1]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(1)});

    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: undefined,
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: promptResponse,
    });

    const {rerender} = mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    expect(
      await screen.findByText(/You have outdated SDKs in your projects/)
    ).toBeInTheDocument();

    // ProjectId no longer matches, so updates should not be shown anymore
    rerender(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert
          sdkUpdates={sdkUpdates}
          selection={{...filters, projects: [2]}}
        />
      </OrganizationContext.Provider>
    );

    expect(
      screen.queryByText(/You have outdated SDKs in your projects/)
    ).not.toBeInTheDocument();
  });

  it('shows prompt if it has never been dismissed', async () => {
    const filters = makeFilterProps({projects: [0]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: undefined,
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: {data: promptResponse},
    });

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    expect(
      await screen.findByText(/You have outdated SDKs in your projects/)
    ).toBeInTheDocument();
  });

  it('never shows prompt if it has been dismissed', async () => {
    const filters = makeFilterProps({projects: [0]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: moment
        .utc()
        .subtract(DEFAULT_SNOOZE_PROMPT_DAYS - 5, 'days')
        .unix(),
      snoozed_ts: undefined,
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: {data: promptResponse},
    });

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    await tick();

    expect(
      screen.queryByText(/You have outdated SDKs in your projects/)
    ).not.toBeInTheDocument();
  });

  it('shows prompt if snoozed_ts days is longer than threshold', async () => {
    const filters = makeFilterProps({projects: [0]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: moment
        .utc()
        .subtract(DEFAULT_SNOOZE_PROMPT_DAYS + 1, 'days')
        .unix(),
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: {data: promptResponse},
    });

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    expect(
      await screen.findByText(/You have outdated SDKs in your projects/)
    ).toBeInTheDocument();
  });

  it('shows prompt if snoozed_ts is shorter than threshold', async () => {
    const filters = makeFilterProps({projects: [0]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: moment
        .utc()
        .subtract(DEFAULT_SNOOZE_PROMPT_DAYS - 2, 'days')
        .unix(),
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: {data: promptResponse},
    });

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    // Flush out our promise and make sure everything renderer
    await tick();

    expect(
      screen.queryByText(/You have outdated SDKs in your projects/)
    ).not.toBeInTheDocument();
  });

  it('shows prompt for all projects when project matches ALL_ACCESS_PROJECTS', async () => {
    // We intentionally missmatch ALL_ACCESS_PROJECTS with projectId in sdkUpdates
    const filters = makeFilterProps({projects: [ALL_ACCESS_PROJECTS]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: undefined,
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: promptResponse,
    });

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    expect(
      await screen.findByText(/You have outdated SDKs in your projects/)
    ).toBeInTheDocument();
  });

  it('dimisses prompt', async () => {
    const filters = makeFilterProps({projects: [0]});
    const sdkUpdates = makeSdkUpdateProps({projectId: String(0)});
    const promptResponse = {
      dismissed_ts: undefined,
      snoozed_ts: undefined,
    };

    MockApiClient.addMockResponse({
      url: '/prompts-activity/',
      body: {data: promptResponse},
    });

    const spy = jest.spyOn(MockApiClient, 'requestPromise');

    mountWithTheme(
      <OrganizationContext.Provider value={TestStubs.Organization()}>
        <InnerGlobalSdkUpdateAlert sdkUpdates={sdkUpdates} selection={filters} />
      </OrganizationContext.Provider>
    );

    userEvent.click(await screen.findByText(/Remind me later/));

    expect(spy.mock.calls[1]).toEqual([
      '/prompts-activity/',
      {
        data: {
          feature: 'sdk_updates',
          organization_id: '3',
          project_id: undefined,
          status: 'snoozed',
        },
        method: 'PUT',
      },
    ]);

    expect(
      screen.queryByText(/You have outdated SDKs in your projects/)
    ).not.toBeInTheDocument();
  });
});
