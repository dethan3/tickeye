import { python } from "pythonia";

const akshare = await python("akshare");

console.log(
  await akshare.stock_zh_a_hist("000001", "daily", "20170301", "20231022", "")
);

process.exit();
