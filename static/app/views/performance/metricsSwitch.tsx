import {createContext, useContext, useState} from 'react';
import styled from '@emotion/styled';

import Feature from 'sentry/components/acl/feature';
import Switch from 'sentry/components/switchButton';
import {t} from 'sentry/locale';
import space from 'sentry/styles/space';
import localStorage from 'sentry/utils/localStorage';
import useOrganization from 'sentry/utils/useOrganization';

const FEATURE_FLAG = 'metrics-performance-ui';

/**
 * This is a temporary component used for debugging metrics data on performance pages.
 * Visible only to small amount of internal users.
 */
function MetricsSwitch({onSwitch}: {onSwitch: () => void}) {
  const organization = useOrganization();
  const {isMetricsData, setIsMetricsData} = useMetricsSwitch();

  function handleToggle() {
    onSwitch();
    setIsMetricsData(!isMetricsData);
  }

  return (
    <Feature features={[FEATURE_FLAG]} organization={organization}>
      <Label>
        {t('Metrics Data')}
        <Switch isActive={isMetricsData} toggle={handleToggle} size="lg" />
      </Label>
    </Feature>
  );
}

const Label = styled('label')`
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0;
  gap: ${space(1)};
  font-weight: normal;
`;

const MetricsSwitchContext = createContext({
  isMetricsData: false,
  isMetricsEnhanced: false,
  setIsMetricsData: (_isMetricsData: boolean) => {},
});

function MetricsSwitchContextContainer({children}: {children: React.ReactNode}) {
  const organization = useOrganization();

  const metricsEnhancedKey = `metrics.performance.enhanced`;
  const [isMetricsEnhanced, setIsMetricsEnhanced] = useState(
    localStorage.getItem(metricsEnhancedKey) === 'true'
  );

  const localStorageKey = `metrics.performance:${organization.slug}`;

  function handleSetIsMetricsData(value: boolean) {
    localStorage.setItem(localStorageKey, value.toString());
    setIsMetricsEnhanced(value);
  }

  return (
    <MetricsSwitchContext.Provider
      value={{
        isMetricsData: false,
        setIsMetricsData: handleSetIsMetricsData,
        isMetricsEnhanced,
      }}
    >
      {children}
    </MetricsSwitchContext.Provider>
  );
}

function useMetricsSwitch() {
  const contextValue = useContext(MetricsSwitchContext);

  return contextValue;
}

export {
  MetricsSwitch,
  MetricsSwitchContextContainer,
  useMetricsSwitch,
  MetricsSwitchContext,
};
