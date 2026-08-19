const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'app.js');
let content = fs.readFileSync(filePath, 'utf8');

const oldFunc = `function renderConvergenceChart(state) {
  const h = state.convergence_history || [];
  if (!convergenceChart || h.length === 0) return;

  convergenceChart.data.labels = h.map(r => 'R' + r.round);
  convergenceChart.data.datasets[0].data = h.map(r => r.accuracy != null ? r.accuracy * 100 : null);
  convergenceChart.data.datasets[1].data = h.map(r => r.loss);
  convergenceChart.update('none');
}`;

const newFunc = `function renderConvergenceChart(state) {
  const h = state.convergence_history || [];
  if (!convergenceChart || h.length === 0) return;

  // Extract accuracy and loss data
  const accData = h.map(r => r.accuracy != null ? r.accuracy * 100 : null).filter(v => v !== null);
  const lossData = h.map(r => r.loss != null ? r.loss : null).filter(v => v !== null);

  convergenceChart.data.labels = h.map(r => 'R' + r.round);
  convergenceChart.data.datasets[0].data = accData;
  convergenceChart.data.datasets[1].data = lossData;

  // Calculate dynamic bounds with 10% padding
  if (accData.length > 0) {
    const accMin = Math.floor(Math.min(...accData) * 0.95);
    const accMax = Math.ceil(Math.max(...accData) * 1.05);
    const accRange = accMax - accMin;
    convergenceChart.options.scales.y.min = Math.max(0, accMin - accRange * 0.1);
    convergenceChart.options.scales.y.max = Math.min(100, accMax + accRange * 0.1);
  }

  if (lossData.length > 0) {
    const lossMin = Math.max(0, Math.floor(Math.min(...lossData) * 0.9));
    const lossMax = Math.ceil(Math.max(...lossData) * 1.1);
    const lossRange = lossMax - lossMin;
    convergenceChart.options.scales.y1.min = lossMin;
    convergenceChart.options.scales.y1.max = lossMax + lossRange * 0.1;
  }

  convergenceChart.update('none');
}`;

if (content.includes(oldFunc)) {
  content = content.replace(oldFunc, newFunc);
  fs.writeFileSync(filePath, content, 'utf8');
  console.log('Successfully updated app.js with dynamic chart scaling!');
} else {
  console.log('Could not find the old function. File may already be updated or encoding mismatch.');
  console.log('Looking for partial match...');
  if (content.includes('function renderConvergenceChart')) {
    console.log('Function exists but format differs.');
  }
}
