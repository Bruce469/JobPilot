// ECharts 按需注册（轻量引入，仅注册用到的图表）
import * as echarts from 'echarts/core'
import { BarChart, FunnelChart, HeatmapChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  FunnelChart,
  HeatmapChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

export { echarts }
