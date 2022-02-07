import * as React from 'react';
import {createContext, useContext, useState} from 'react';
import {browserHistory} from 'react-router';
import styled from '@emotion/styled';
import {Location} from 'history';
import isEqual from 'lodash/isEqual';

import Feature from 'sentry/components/acl/feature';
import Alert from 'sentry/components/alert';
import Button from 'sentry/components/button';
import Switch from 'sentry/components/switchButton';
import Tag from 'sentry/components/tag';
import {IconUpgrade} from 'sentry/icons';
import {t, tct} from 'sentry/locale';
import space from 'sentry/styles/space';
import EventView from 'sentry/utils/discover/eventView';
import {decodeScalar} from 'sentry/utils/queryString';
import {MutableSearch} from 'sentry/utils/tokenizeSearch';
import useOrganization from 'sentry/utils/useOrganization';
import usePrevious from 'sentry/utils/usePrevious';

const FEATURE_FLAG = 'metrics-performance-ui';

/**
 * This is a temporary component used for debugging metrics data on performance pages.
 * Visible only to small amount of internal users.
 */
function MetricsSwitch({onSwitch}: {onSwitch: () => void}) {
  const organization = useOrganization();
  const {isMetricsEnhanced, setIsMetricsData} = useMetricsSwitch();

  function handleToggle() {
    onSwitch();
    setIsMetricsData(!isMetricsEnhanced);
  }

  return null;

  // return (
  //   <Feature features={[FEATURE_FLAG]} organization={organization}>
  //     <Label>
  //       {t('Metrics Data')}
  //       <Switch isActive={isMetricsEnhanced} toggle={handleToggle} size="lg" />
  //     </Label>
  //   </Feature>
  // );
}

const checkQueryMEPSable = (_: Location, eventView?: EventView) => {
  if (!eventView) {
    return null;
  }

  const tagKeyAllowList = [
    'transaction.op',
    'transaction.status',
    'is_user_miserable',
    'http.method',
  ];

  const conditions = new MutableSearch(eventView.query);
  const conditionFilters = conditions.getFilterKeys();
  const result = conditionFilters.every(c => tagKeyAllowList.includes(c));

  return result;
};

const Label = styled('label')`
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0;
  gap: ${space(1)};
  font-weight: normal;
`;

export type MetricSwitchContextType = {
  isMetricsData: boolean;
  isMetricsEnhanced: boolean;
  hasMEPSChanged: boolean;
  eventView?: EventView;
  isQueryMEPS?: boolean;
  setIsMetricsData: (a: boolean) => void;
  setEventView: (e: EventView) => void;
  setQueryMEPS: (a: boolean) => void;
};
const MetricsSwitchContext = createContext<MetricSwitchContextType>({
  isMetricsData: false,
  isMetricsEnhanced: true,
  hasMEPSChanged: false,
  eventView: undefined,
  isQueryMEPS: undefined,
  setIsMetricsData: (_isMetricsData: boolean) => {},
  setEventView: (_isMetricsData: EventView) => {},
  setQueryMEPS: (_: boolean) => {},
});

function MetricsSwitchContextContainer({
  children,
  location,
}: {
  location: Location;
  children: React.ReactNode;
}) {
  const [eventView, _setEventView] = useState<EventView | undefined>(undefined);
  const setEventView = (e: EventView) => {
    setTimeout(() => {
      _setEventView(e);
      // Put it in timeout since this is a hack to test ui anyway.
    }, 100);
  };

  const [isQueryMEPS, _setQueryMEPS] = useState<boolean | null>(null);

  const setQueryMEPS = (b: boolean) => {
    _setQueryMEPS(b);
  };

  // const isQueryMEPS = checkQueryMEPSable(location, eventView);
  const previousMEPS = usePrevious(isQueryMEPS);
  const hasMEPSChanged =
    previousMEPS !== null && isQueryMEPS !== null && !isEqual(isQueryMEPS, previousMEPS);

  const [isMetricsEnhanced, setIsMetricsEnhanced] = useState(
    true
    // decodeScalar(location.query.metricsEnhanced) === 'true'
  );

  function handleSetIsMetricsData(value: boolean) {
    if (value) {
      browserHistory.push({
        ...location,
        query: {
          ...location.query,
          metricsEnhanced: true,
        },
      });
    } else {
      browserHistory.push({
        ...location,
        query: {
          ...location.query,
          metricsEnhanced: false,
        },
      });
    }
    setIsMetricsEnhanced(value);
  }

  return (
    <MetricsSwitchContext.Provider
      value={{
        isMetricsData: false,
        setIsMetricsData: handleSetIsMetricsData,
        isMetricsEnhanced,
        hasMEPSChanged,
        eventView,
        isQueryMEPS,
        setEventView,
        setQueryMEPS,
      }}
    >
      {children}
    </MetricsSwitchContext.Provider>
  );
}

function MEPSPill() {
  const {isQueryMEPS} = useMetricsSwitch();

  if (isQueryMEPS) {
    return null;
  }
  return (
    <Tag
      type="default"
      tooltipText="The search conditions applied are only applicable to sampled transaction data. To edit sampling, to to settings."
    >
      {'Sampled'}
    </Tag>
  );
}

function useMetricsSwitch() {
  const contextValue = useContext(MetricsSwitchContext);

  return contextValue;
}

function MEPSAlert() {
  return null;
  // const {hasMEPSChanged} = useMetricsSwitch();
  // if (hasMEPSChanged) {
  //   return (
  //     <Alert type="info" icon={<IconUpgrade />}>
  //       <Content>
  //         {tct(
  //           `We've automatically adjusted your visualizations to reflect a sampled set of transactions. To adjust sampling filters, go to [link:settings] `,
  //           {
  //             link: (
  //               <Button
  //                 priority="link"
  //                 size="zero"
  //                 title={t('Sampling Settings')}
  //                 onClick={() => {}}
  //               >
  //                 {t('settings')}
  //               </Button>
  //             ),
  //           }
  //         )}
  //         <Actions> </Actions>
  //       </Content>
  //     </Alert>
  //   );
  // }
  // return null;
}

const Content = styled('div')`
  display: flex;
  flex-wrap: wrap;

  @media (min-width: ${p => p.theme.breakpoints[0]}) {
    justify-content: space-between;
  }
`;

const Actions = styled('div')`
  display: grid;
  grid-template-columns: repeat(3, max-content);
  gap: ${space(1)};
`;

export {
  MetricsSwitch,
  MetricsSwitchContextContainer,
  useMetricsSwitch,
  MetricsSwitchContext,
  MEPSAlert,
  MEPSPill,
};
