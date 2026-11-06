(() => {
'use strict';
const el=document.getElementById('world-map');if(!el)return;
const readout=document.getElementById('map-readout'),select=document.getElementById('map-country');
if(!window.L){readout.textContent='Map could not load. Please refresh the page.';return;}
const map=L.map(el,{minZoom:1,maxZoom:8,zoomSnap:.25,scrollWheelZoom:false,attributionControl:true,worldCopyJump:true});
map.attributionControl.setPrefix(false);
map.attributionControl.addAttribution('Boundaries: Natural Earth · Public domain');
const world=[[-57,-175],[78,180]];
const reset=()=>map.fitBounds(world,{padding:[10,10],animate:false});reset();
const countryLayers=new Map();let selected=null;
function choose(layer){if(selected)selected.setStyle({fillColor:'#426c56',fillOpacity:.7,weight:.7});selected=layer;layer.setStyle({fillColor:'#c4dfaa',fillOpacity:.95,weight:1.5});const name=layer.feature.properties.name;select.value=name;map.fitBounds(layer.getBounds(),{padding:[26,26],maxZoom:6,animate:!matchMedia('(prefers-reduced-motion: reduce)').matches});readout.textContent=name+' · Geographic explorer';}
fetch('world-countries.json').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>{
L.geoJSON(data,{style:{color:'#8eaf93',weight:.7,fillColor:'#426c56',fillOpacity:.7},onEachFeature:(feature,layer)=>{const name=feature.properties.name;if(name==='Antarctica')return;countryLayers.set(name,layer);layer.bindTooltip(name,{sticky:true,direction:'top'});layer.on('click',()=>choose(layer));}}).addTo(map);
[...countryLayers.keys()].sort().forEach(name=>{const option=document.createElement('option');option.value=name;option.textContent=name;select.append(option);});
}).catch(()=>{readout.textContent='Country boundaries could not load. Please refresh to try again.';});
select.addEventListener('change',()=>{const layer=countryLayers.get(select.value);if(layer)choose(layer);});
document.getElementById('map-world').addEventListener('click',()=>{if(selected)selected.setStyle({fillColor:'#426c56',fillOpacity:.7,weight:.7});selected=null;select.value='';reset();readout.textContent='Worldwide view · Select a country to explore';});
const resize=()=>{if(el.getBoundingClientRect().width){map.invalidateSize({pan:false});if(!selected)reset();}};
new ResizeObserver(resize).observe(el);
new MutationObserver(resize).observe(el.closest('.showcase-slide'),{attributes:true,attributeFilter:['hidden']});
})();
