DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'designkp') THEN
    CREATE ROLE designkp LOGIN PASSWORD 'designkp_pass_ChangeMe';
  ELSE
    ALTER ROLE designkp WITH LOGIN PASSWORD 'designkp_pass_ChangeMe';
  END IF;
END
$$;

SELECT 'role_ready' AS status;
