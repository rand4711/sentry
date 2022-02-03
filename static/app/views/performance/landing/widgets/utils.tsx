import {PROJECT_PERFORMANCE_TYPE} from '../../utils';

import {PerformanceWidgetProps} from './types';
import {PerformanceWidgetSetting} from './widgetDefinitions';

const MEPSable = [
  PerformanceWidgetSetting.P50_DURATION_AREA,
  PerformanceWidgetSetting.P75_DURATION_AREA,
  PerformanceWidgetSetting.P95_DURATION_AREA,
  PerformanceWidgetSetting.P75_LCP_AREA,
  PerformanceWidgetSetting.TPM_AREA,
];
export const metricsSettings = (
  props: PerformanceWidgetProps
): Record<string, string> | undefined => {
  if (MEPSable.includes(props.chartSetting)) {
    return {
      metricsEnhanced: '1',
    };
  }
  return undefined;
};

export const eventsRequestQueryProps = [
  'children',
  'organization',
  'yAxis',
  'period',
  'start',
  'end',
  'environment',
  'project',
] as const;

function setWidgetStorageObject(localObject: Record<string, string>) {
  localStorage.setItem(getContainerLocalStorageObjectKey, JSON.stringify(localObject));
}

const getContainerLocalStorageObjectKey = 'landing-chart-container';
const getContainerKey = (
  index: number,
  performanceType: PROJECT_PERFORMANCE_TYPE,
  height: number
) => `landing-chart-container#${performanceType}#${height}#${index}`;

function getWidgetStorageObject() {
  const localObject = JSON.parse(
    localStorage.getItem(getContainerLocalStorageObjectKey) || '{}'
  );
  return localObject;
}

export const getChartSetting = (
  index: number,
  height: number,
  performanceType: PROJECT_PERFORMANCE_TYPE,
  defaultType: PerformanceWidgetSetting,
  forceDefaultChartSetting?: boolean // Used for testing.
): PerformanceWidgetSetting => {
  if (forceDefaultChartSetting) {
    return defaultType;
  }
  const key = getContainerKey(index, performanceType, height);
  const localObject = getWidgetStorageObject();
  const value = localObject?.[key];

  if (
    value &&
    Object.values(PerformanceWidgetSetting).includes(value as PerformanceWidgetSetting)
  ) {
    const _value: PerformanceWidgetSetting = value as PerformanceWidgetSetting;
    return _value;
  }
  return defaultType;
};
export const _setChartSetting = (
  index: number,
  height: number,
  performanceType: PROJECT_PERFORMANCE_TYPE,
  setting: PerformanceWidgetSetting
) => {
  const key = getContainerKey(index, performanceType, height);
  const localObject = getWidgetStorageObject();
  localObject[key] = setting;

  setWidgetStorageObject(localObject);
};
