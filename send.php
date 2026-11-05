<?php
// Приём заявок с сайта Travel&K и отправка в Telegram.
// 1) Скопируйте config.sample.php в config.php и впишите токен бота и chat_id (см. README.md).
header('Content-Type: application/json; charset=utf-8');
$cfgFile=__DIR__.'/config.php';
if(!file_exists($cfgFile)){http_response_code(503);echo json_encode(['ok'=>false,'error'=>'not configured']);exit;}
$cfg=require $cfgFile;
if($_SERVER['REQUEST_METHOD']!=='POST'){http_response_code(405);echo json_encode(['ok'=>false]);exit;}
$d=json_decode(file_get_contents('php://input'),true);
if(!is_array($d)||empty($d['name'])||empty($d['contact'])){http_response_code(422);echo json_encode(['ok'=>false,'error'=>'invalid']);exit;}
if(!empty($d['website'])){echo json_encode(['ok'=>true]);exit;} // honeypot
// простое ограничение частоты: не чаще 1 заявки в 20 секунд с одного IP
$ip=$_SERVER['REMOTE_ADDR']??'0';$lock=sys_get_temp_dir().'/tk_'.md5($ip);
if(file_exists($lock)&&time()-filemtime($lock)<20){http_response_code(429);echo json_encode(['ok'=>false,'error'=>'rate']);exit;}
touch($lock);
function c($s){return mb_substr(trim(strip_tags((string)$s)),0,500);}
$L=['name'=>'Имя','contact'=>'Контакт','tour'=>'Что интересует','date'=>'Дата','adults'=>'Взрослых','kids'=>'Детей','hotel'=>'Отель / район','comment'=>'Комментарий','promo'=>'Промокод','page'=>'Страница'];
$t="🆕 Заявка с сайта Travel&K\n";
foreach($L as $k=>$n){if(!empty($d[$k]))$t.="$n: ".c($d[$k])."\n";}
$t.="IP: $ip";
$url="https://api.telegram.org/bot{$cfg['bot_token']}/sendMessage";
$ctx=stream_context_create(['http'=>['method'=>'POST','header'=>"Content-Type: application/x-www-form-urlencoded\r\n",'content'=>http_build_query(['chat_id'=>$cfg['chat_id'],'text'=>$t]),'timeout'=>8]]);
$r=@file_get_contents($url,false,$ctx);
$j=$r?json_decode($r,true):null;
if($j&&!empty($j['ok'])){echo json_encode(['ok'=>true]);}else{http_response_code(502);echo json_encode(['ok'=>false]);}
