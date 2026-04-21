import pkg from "pg";
const { Pool } = pkg;

const pool = new Pool({
  host: "localhost",
  port: 5433,                
  user: "appuser",
  password: "apppassword",
  database: "appdb",
});

export default {
  query: (text, params) => pool.query(text, params),
};
